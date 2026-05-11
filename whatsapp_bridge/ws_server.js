'use strict';

/**
 * WebSocket relay server for the WhatsApp bridge.
 *
 * Exposes the WhatsApp bridge state over WebSocket so future clients
 * (e.g. a native notification service) can subscribe to events without
 * polling the HTTP REST API.
 *
 * Currently a thin adapter over the bridge.js HTTP server.
 * Start alongside bridge.js if WebSocket access is needed; it is not
 * required for normal AuraBot operation (the Python backend uses HTTP).
 *
 * Usage:
 *   node ws_server.js [port]   (default port: 8767)
 */

const http = require('http');
const { WebSocketServer } = require('ws');

const WS_PORT = parseInt(process.argv[2] || '8767', 10);
const BRIDGE_BASE = 'http://127.0.0.1:8766';

const server = http.createServer((_req, res) => {
  res.writeHead(200);
  res.end('AuraBot WebSocket relay');
});

const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
  console.log('[ws_server] Client connected');

  // Send current bridge status on connect
  _fetchBridgeStatus().then(status => {
    if (ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify({ type: 'status', data: status }));
    }
  });

  ws.on('message', async (raw) => {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }

    if (msg.type === 'get_status') {
      const status = await _fetchBridgeStatus();
      ws.send(JSON.stringify({ type: 'status', data: status }));
    } else if (msg.type === 'get_qr') {
      const qr = await _fetchJson('/qr');
      ws.send(JSON.stringify({ type: 'qr', data: qr }));
    }
  });

  ws.on('close', () => console.log('[ws_server] Client disconnected'));
});

server.listen(WS_PORT, '127.0.0.1', () => {
  console.log(`[ws_server] Listening on ws://127.0.0.1:${WS_PORT}`);
});


// ── Helpers ──────────────────────────────────────────────────────────────────

function _fetchJson(path) {
  return new Promise((resolve) => {
    http.get(`${BRIDGE_BASE}${path}`, (res) => {
      let body = '';
      res.on('data', d => { body += d; });
      res.on('end', () => {
        try { resolve(JSON.parse(body)); } catch { resolve({}); }
      });
    }).on('error', () => resolve({}));
  });
}

function _fetchBridgeStatus() {
  return _fetchJson('/status');
}
