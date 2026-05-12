'use strict';

/**
 * AuraBot WhatsApp bridge — Phase 6.
 *
 * Runs as a child process (Node.js HTTP server on port 8766).
 * Uses whatsapp-web.js + LocalAuth so the user only scans the QR code once.
 * Session is persisted in ~/.aurabot/whatsapp/.
 *
 * HTTP API:
 *   GET  /wa/status      -> {connected, bridge_running, name, phone}
 *   GET  /wa/qr          -> {connected, qr}   (qr = base64 data URL or null)
 *   GET  /wa/chats       -> [{id, name, unreadCount, lastMessage, timestamp, isGroup}]
 *   GET  /wa/messages    -> [{id, from, fromMe, body, timestamp, type}]
 *                          ?chatId=<id>&limit=<n>
 *   POST /wa/disconnect  -> {ok}
 */

const http = require('http');
const path = require('path');
const os   = require('os');

const { Client, LocalAuth } = require('whatsapp-web.js');
const QRCode = require('qrcode');

const PORT       = 8766;
const SESSION_DIR = path.join(os.homedir(), '.aurabot', 'whatsapp');

// ── State ──────────────────────────────────────────────────────────────────

let client     = null;
let qrDataUrl  = null;   // base64 PNG data URL, set while waiting for scan
let connected  = false;
let clientInfo = null;
let initialising = false;


// ── WhatsApp client ────────────────────────────────────────────────────────

async function initClient() {
  if (initialising) return;
  initialising = true;

  client = new Client({
    authStrategy: new LocalAuth({ dataPath: SESSION_DIR }),
    puppeteer: {
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
      ],
    },
  });

  client.on('qr', async (qr) => {
    try {
      qrDataUrl = await QRCode.toDataURL(qr, { width: 256 });
    } catch (_) {
      qrDataUrl = null;
    }
    connected = false;
    console.log('[WA Bridge] QR ready — waiting for phone scan');
  });

  client.on('authenticated', () => {
    console.log('[WA Bridge] Authenticated');
    qrDataUrl = null;
  });

  client.on('ready', () => {
    connected  = true;
    qrDataUrl  = null;
    clientInfo = client.info;
    initialising = false;
    console.log('[WA Bridge] Connected as:', clientInfo?.pushname || 'unknown');
  });

  client.on('auth_failure', (msg) => {
    console.error('[WA Bridge] Auth failure:', msg);
    connected    = false;
    initialising = false;
  });

  client.on('disconnected', (reason) => {
    console.log('[WA Bridge] Disconnected:', reason);
    connected    = false;
    clientInfo   = null;
    initialising = false;
    // Auto-restart in 8 seconds to show a fresh QR code
    setTimeout(initClient, 8000);
  });

  try {
    await client.initialize();
  } catch (e) {
    console.error('[WA Bridge] Initialize error:', e.message);
    initialising = false;
    // Retry after delay
    setTimeout(initClient, 15000);
  }
}


// ── HTTP helpers ───────────────────────────────────────────────────────────

function json(res, code, data) {
  const body = JSON.stringify(data);
  res.writeHead(code, {
    'Content-Type':                'application/json',
    'Access-Control-Allow-Origin': '*',
  });
  res.end(body);
}

function readBody(req) {
  return new Promise(resolve => {
    let data = '';
    req.on('data', chunk => { data += chunk; });
    req.on('end', () => resolve(data));
  });
}


// ── HTTP server ────────────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const [urlPath, queryStr] = req.url.split('?');
  const qs = Object.fromEntries(new URLSearchParams(queryStr || ''));

  // ── GET /wa/status ─────────────────────────────────────────────────────
  if (urlPath === '/wa/status') {
    return json(res, 200, {
      bridge_running: true,
      connected,
      name:  clientInfo?.pushname || null,
      phone: clientInfo?.wid?.user || null,
    });
  }

  // ── GET /wa/qr ─────────────────────────────────────────────────────────
  if (urlPath === '/wa/qr') {
    return json(res, 200, {
      connected,
      qr:           connected ? null : (qrDataUrl || null),
      initialising: initialising && !qrDataUrl,
    });
  }

  // ── GET /wa/chats ──────────────────────────────────────────────────────
  // ?limit=N (default 100). Returns all chats sorted by most recent first.
  if (urlPath === '/wa/chats') {
    if (!connected || !client) return json(res, 503, { error: 'Not connected' });
    try {
      const limit = Math.min(parseInt(qs.limit || '100', 10), 500);
      const chats = await client.getChats();
      return json(res, 200, chats.slice(0, limit).map(c => ({
        id:          c.id._serialized,
        name:        c.name || c.id.user,
        unreadCount: c.unreadCount || 0,
        lastMessage: c.lastMessage?.body?.slice(0, 200) || '',
        timestamp:   c.timestamp || 0,
        isGroup:     c.isGroup || false,
      })));
    } catch (e) {
      return json(res, 500, { error: e.message });
    }
  }

  // ── GET /wa/unread ─────────────────────────────────────────────────────
  // Scans ALL chats, returns only those with unread > 0.
  // Each entry includes recent unread message bodies for context.
  if (urlPath === '/wa/unread') {
    if (!connected || !client) return json(res, 503, { error: 'Not connected' });
    try {
      const allChats = await client.getChats();
      const unread   = allChats.filter(c => (c.unreadCount || 0) > 0);

      const results = await Promise.all(unread.map(async c => {
        let recentMsgs = [];
        try {
          // Fetch enough messages to cover all unread + a couple for context
          const fetchCount = Math.max(c.unreadCount + 3, 8);
          const msgs = await c.fetchMessages({ limit: fetchCount });
          // Only return the actual unread tail (fromMe:false is a heuristic; keep all)
          recentMsgs = msgs.slice(-Math.min(fetchCount, msgs.length)).map(m => ({
            body:      (m.body || '').slice(0, 300),
            fromMe:    m.fromMe,
            timestamp: m.timestamp,
            type:      m.type,
          }));
        } catch (_) { /* non-critical */ }

        return {
          id:          c.id._serialized,
          name:        c.name || c.id.user,
          unreadCount: c.unreadCount || 0,
          lastMessage: c.lastMessage?.body?.slice(0, 300) || '',
          timestamp:   c.timestamp || 0,
          isGroup:     c.isGroup || false,
          messages:    recentMsgs,
        };
      }));

      // Sort by most recent first
      results.sort((a, b) => b.timestamp - a.timestamp);
      return json(res, 200, results);
    } catch (e) {
      return json(res, 500, { error: e.message });
    }
  }

  // ── GET /wa/recent ─────────────────────────────────────────────────────
  // Returns top N chats (default 25) with their last M messages each.
  // ?chats=N&messages=M
  if (urlPath === '/wa/recent') {
    if (!connected || !client) return json(res, 503, { error: 'Not connected' });
    try {
      const chatLimit = Math.min(parseInt(qs.chats    || '25', 10), 100);
      const msgLimit  = Math.min(parseInt(qs.messages || '15', 10), 50);
      const allChats  = await client.getChats();
      const slice     = allChats.slice(0, chatLimit);

      const results = await Promise.all(slice.map(async c => {
        let messages = [];
        try {
          const msgs = await c.fetchMessages({ limit: msgLimit });
          messages = msgs.map(m => ({
            body:      (m.body || '').slice(0, 500),
            fromMe:    m.fromMe,
            timestamp: m.timestamp,
            type:      m.type,
          }));
        } catch (_) {}
        return {
          id:          c.id._serialized,
          name:        c.name || c.id.user,
          unreadCount: c.unreadCount || 0,
          timestamp:   c.timestamp   || 0,
          isGroup:     c.isGroup     || false,
          messages,
        };
      }));

      return json(res, 200, results);
    } catch (e) {
      return json(res, 500, { error: e.message });
    }
  }

  // ── GET /wa/messages ───────────────────────────────────────────────────
  if (urlPath === '/wa/messages') {
    if (!connected || !client) return json(res, 503, { error: 'Not connected' });
    const chatId = qs.chatId;
    const limit  = Math.min(parseInt(qs.limit || '30', 10), 100);
    if (!chatId) return json(res, 400, { error: 'chatId required' });
    try {
      const chat = await client.getChatById(chatId);
      const msgs = await chat.fetchMessages({ limit });
      return json(res, 200, msgs.map(m => ({
        id:        m.id._serialized,
        from:      m.from,
        fromMe:    m.fromMe,
        body:      m.body || '',
        timestamp: m.timestamp,
        type:      m.type,
      })));
    } catch (e) {
      return json(res, 500, { error: e.message });
    }
  }

  // ── POST /wa/disconnect ────────────────────────────────────────────────
  if (urlPath === '/wa/disconnect') {
    try {
      if (client) { await client.logout(); }
      connected  = false;
      clientInfo = null;
      qrDataUrl  = null;
      return json(res, 200, { ok: true });
    } catch (e) {
      return json(res, 500, { error: e.message });
    }
  }

  return json(res, 404, { error: 'Not found' });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[WA Bridge] HTTP server on http://127.0.0.1:${PORT}`);
  initClient().catch(e => {
    console.error('[WA Bridge] Startup error:', e.message);
    initialising = false;
  });
});

// ── Graceful shutdown ──────────────────────────────────────────────────────

async function shutdown() {
  console.log('[WA Bridge] Shutting down...');
  server.close();
  try { if (client) await client.destroy(); } catch (_) {}
  process.exit(0);
}
process.on('SIGTERM', shutdown);
process.on('SIGINT',  shutdown);
