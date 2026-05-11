'use strict';

const BACKEND = 'http://127.0.0.1:8765';

// ── State ──────────────────────────────────────────────────────────────────
let backendReady = false;
let sending      = false;

// ── DOM refs ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const screens = {
  loading: $('loading-screen'),
  error:   $('error-screen'),
  main:    $('main-content'),
};

// ── Screen switching ───────────────────────────────────────────────────────
function showScreen(name) {
  Object.entries(screens).forEach(([k, el]) => {
    el.classList.toggle('active', k === name);
  });
}

function setStatus(label, dotClass) {
  const dot  = $('status-dot');
  const text = $('status-text');
  if (dot)  { dot.className = `status-dot ${dotClass}`; }
  if (text) { text.textContent = label; }
}

// ── Time helpers ───────────────────────────────────────────────────────────
function fmtTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

// ── Message rendering ──────────────────────────────────────────────────────
function appendMessage({ role, text, expression = 'idle', animate = true }) {
  const list = $('messages');
  if (!list) return;

  const row = document.createElement('div');
  row.className = `msg-row ${role}`;

  const time = document.createElement('div');
  time.className = 'msg-time';
  time.textContent = fmtTime(new Date());

  if (role === 'bot') {
    const avatar = document.createElement('img');
    avatar.src       = `avatars/${expression}.svg`;
    avatar.className = 'msg-avatar';
    avatar.alt       = '';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.textContent = text;

    const copy = document.createElement('button');
    copy.className   = 'copy-btn no-drag';
    copy.textContent = 'Copy';
    copy.addEventListener('click', () => {
      navigator.clipboard.writeText(text).catch(() => {});
      copy.textContent = 'Copied!';
      setTimeout(() => { copy.textContent = 'Copy'; }, 1500);
    });
    bubble.appendChild(copy);

    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display:flex;flex-direction:column;flex:1;min-width:0;';
    wrapper.appendChild(bubble);
    wrapper.appendChild(time);

    row.appendChild(avatar);
    row.appendChild(wrapper);

    if (expression) AvatarController.setExpression(expression);

  } else {
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.textContent = text;

    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display:flex;flex-direction:column;align-items:flex-end;max-width:82%;';
    wrapper.appendChild(bubble);
    wrapper.appendChild(time);

    row.appendChild(wrapper);
  }

  list.appendChild(row);
  list.scrollTop = list.scrollHeight;
}

function showTypingIndicator() {
  const list = $('messages');
  if (!list) return null;

  const row = document.createElement('div');
  row.id = 'typing-row';
  row.className = 'msg-row bot';

  const avatar = document.createElement('img');
  avatar.src = 'avatars/thinking.svg';
  avatar.className = 'msg-avatar';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble typing';
  bubble.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';

  row.appendChild(avatar);
  row.appendChild(bubble);
  list.appendChild(row);
  list.scrollTop = list.scrollHeight;

  AvatarController.setExpression('thinking');
  setStatus('Thinking…', 'status-thinking');

  return row;
}

function removeTypingIndicator() {
  $('typing-row')?.remove();
}

// ── Welcome message ────────────────────────────────────────────────────────
function showWelcome() {
  const list = $('messages');
  if (!list) return;

  const wrap = document.createElement('div');
  wrap.className = 'greeting-msg';
  wrap.innerHTML = `
    <img src="avatars/happy.svg" class="greeting-avatar" alt="">
    <p class="greeting-text">
      ${greeting()}! I'm AuraBot, your AI chief-of-staff.<br>
      Ask me anything, or head to ⚙ Settings to connect your accounts.
    </p>
  `;
  list.appendChild(wrap);

  // Follow up with first bot message
  appendMessage({
    role: 'bot',
    text: "Hi there! I'm ready to help. What's on your mind today?",
    expression: 'happy',
  });
}

// ── SSE streaming send ─────────────────────────────────────────────────────
async function sendMessage() {
  if (sending || !backendReady) return;

  const input = $('user-input');
  const text  = input.value.trim();
  if (!text) return;

  input.value = '';
  input.style.height = '';
  sending = true;
  $('btn-send').disabled = true;

  appendMessage({ role: 'user', text });
  showTypingIndicator();

  // Build the streaming bot bubble (hidden until first chunk)
  const list = $('messages');
  let botRow    = null;
  let botBubble = null;
  let botText   = '';

  function ensureBotBubble() {
    if (botBubble) return;
    removeTypingIndicator();

    botRow = document.createElement('div');
    botRow.className = 'msg-row bot';

    const avatar = document.createElement('img');
    avatar.src       = 'avatars/thinking.svg';
    avatar.id        = 'stream-avatar';
    avatar.className = 'msg-avatar';

    botBubble = document.createElement('div');
    botBubble.className = 'msg-bubble';

    const copy = document.createElement('button');
    copy.className   = 'copy-btn no-drag';
    copy.textContent = 'Copy';
    copy.addEventListener('click', () => {
      navigator.clipboard.writeText(botText).catch(() => {});
      copy.textContent = 'Copied!';
      setTimeout(() => { copy.textContent = 'Copy'; }, 1500);
    });
    botBubble.appendChild(copy);

    const timeEl = document.createElement('div');
    timeEl.className   = 'msg-time';
    timeEl.textContent = fmtTime(new Date());

    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display:flex;flex-direction:column;flex:1;min-width:0;';
    wrapper.appendChild(botBubble);
    wrapper.appendChild(timeEl);

    botRow.appendChild(avatar);
    botRow.appendChild(wrapper);
    list.appendChild(botRow);
  }

  function appendChunk(chunk) {
    ensureBotBubble();
    botText += chunk;
    // Rebuild text node before the copy button
    const copy = botBubble.querySelector('.copy-btn');
    botBubble.childNodes.forEach(n => { if (n.nodeType === Node.TEXT_NODE) n.remove(); });
    botBubble.insertBefore(document.createTextNode(botText), copy);
    list.scrollTop = list.scrollHeight;
  }

  function showToolIndicator(tool, query) {
    ensureBotBubble();
    let indicator = $('tool-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id        = 'tool-indicator';
      indicator.className = 'tool-indicator';
      list.appendChild(indicator);
    }
    if (tool === 'check_email') {
      indicator.textContent = 'Reading inbox…';
      setStatus('Reading email…', 'status-thinking');
    } else if (tool === 'check_calendar') {
      indicator.textContent = 'Reading calendar…';
      setStatus('Reading calendar…', 'status-thinking');
    } else if (tool === 'check_whatsapp') {
      indicator.textContent = 'Reading WhatsApp chats…';
      setStatus('Reading WhatsApp…', 'status-thinking');
    } else {
      indicator.textContent = `Searching: ${query}`;
      setStatus('Searching…', 'status-thinking');
    }
    indicator.style.display = 'block';
    list.scrollTop = list.scrollHeight;
    AvatarController.setExpression('focused');
  }

  function hideToolIndicator() {
    const indicator = $('tool-indicator');
    if (indicator) indicator.style.display = 'none';
    setStatus('Thinking…', 'status-thinking');
  }

  try {
    const res = await fetch(`${BACKEND}/chat`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message: text }),
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop(); // keep incomplete tail

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data:')) continue;
        let event;
        try { event = JSON.parse(line.slice(5).trim()); }
        catch (_) { continue; }

        switch (event.type) {
          case 'chunk':
            appendChunk(event.text);
            break;

          case 'tool_start':
            showToolIndicator(event.tool || '', event.query || '');
            break;

          case 'tool_done':
            hideToolIndicator();
            break;

          case 'error_replace':
            ensureBotBubble();
            botText = event.text;
            const copyBtn = botBubble.querySelector('.copy-btn');
            botBubble.childNodes.forEach(n => { if (n.nodeType === Node.TEXT_NODE) n.remove(); });
            botBubble.insertBefore(document.createTextNode(botText), copyBtn);
            AvatarController.setExpression('confused');
            break;

          case 'done': {
            const expr = event.expression || 'idle';
            if ($('stream-avatar')) $('stream-avatar').src = `avatars/${expr}.svg`;
            AvatarController.setExpression(expr);
            setStatus('Ready', 'status-ready');
            hideToolIndicator();
            $('tool-indicator')?.remove();
            break;
          }
        }
      }
    }

    // If no content was streamed (empty response), show fallback
    if (!botText) {
      removeTypingIndicator();
      appendMessage({ role: 'bot', text: 'No response received.', expression: 'confused' });
    }

  } catch (err) {
    removeTypingIndicator();
    appendMessage({
      role: 'bot',
      text: `Sorry, I couldn't reach the backend. ${err.message}. Try restarting the app.`,
      expression: 'confused',
    });
    setStatus('Error', 'status-error');
  }

  sending = false;
  $('btn-send').disabled = false;
  input.focus();
}

// ── Input auto-resize ──────────────────────────────────────────────────────
function initInputResize() {
  const input = $('user-input');
  if (!input) return;

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    const maxH = parseInt(getComputedStyle(input).maxHeight, 10) || 120;
    input.style.height = Math.min(input.scrollHeight, maxH) + 'px';
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

// ── Window controls ────────────────────────────────────────────────────────
function initWindowControls() {
  if (!window.electronAPI) return;
  $('btn-close')?.addEventListener('click', () => window.electronAPI.close());

  // Pin (always-on-top) — sync initial state then highlight when active
  const pinBtn = $('btn-pin');
  if (pinBtn) {
    window.electronAPI.getAlwaysOnTop().then(on => setPinState(on));
    pinBtn.addEventListener('click', () => window.electronAPI.toggleAlwaysOnTop());
    window.electronAPI.onAlwaysOnTopChanged(on => setPinState(on));
  }

  // Collapse / expand
  const colBtn = $('btn-collapse');
  if (colBtn) {
    colBtn.addEventListener('click', () => window.electronAPI.toggleCompact());
    window.electronAPI.onCompactChanged(compact => setCompactState(compact));
  }
}

function setPinState(on) {
  const btn = $('btn-pin');
  if (!btn) return;
  btn.title = on ? 'Unpin (always on top)' : 'Pin (always on top)';
  btn.classList.toggle('pinned', on);
}

function setCompactState(compact) {
  const btn = $('btn-collapse');
  if (btn) {
    btn.textContent = compact ? '▲' : '▼';
    btn.title       = compact ? 'Expand' : 'Collapse';
  }
  // Also hide/show content so the strip looks clean when collapsed
  const main = $('main-content');
  if (main) main.style.display = compact ? 'none' : '';
}

// ── File attach (Phase 8 — stub for now) ──────────────────────────────────
function initFileAttach() {
  const btn   = $('btn-attach');
  const input = $('file-input');
  if (!btn || !input) return;

  btn.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    const file = input.files?.[0];
    if (!file) return;
    // Phase 8 will handle upload — for now just show the filename
    appendMessage({ role: 'user', text: `[Attached: ${file.name}]` });
    appendMessage({
      role: 'bot',
      text: 'File attachments will be fully supported in Phase 8. For now, paste the text content directly.',
      expression: 'focused',
    });
    input.value = '';
  });
}

// ── Backend lifecycle (via Electron IPC) ───────────────────────────────────
function initBackendEvents() {
  if (!window.electronAPI) {
    // Running outside Electron (e.g. browser dev) — auto-ready
    backendReady = true;
    showScreen('main');
    showWelcome();
    setStatus('Ready', 'status-ready');
    NudgesPanel.startPolling();
    return;
  }

  window.electronAPI.onLoadingStatus(msg => {
    const sub = document.querySelector('.loading-sub');
    if (sub) sub.textContent = msg;
  });

  window.electronAPI.onBackendReady(() => {
    backendReady = true;
    showScreen('main');
    showWelcome();
    setStatus('Ready', 'status-ready');
    AvatarController.setExpression('happy');
    NudgesPanel.startPolling();
  });

  window.electronAPI.onBackendError(msg => {
    showScreen('error');
    $('error-message').textContent = msg;
    setStatus('Error', 'status-error');
  });
}

// ── Retry button ───────────────────────────────────────────────────────────
function initRetry() {
  $('btn-retry')?.addEventListener('click', () => {
    showScreen('loading');
    setStatus('Starting…', 'status-loading');
    setTimeout(() => location.reload(), 500);
  });
}

// ── Permission dialog ──────────────────────────────────────────────────────
/**
 * Request a permission from the user via an inline chat dialog.
 * Returns a Promise that resolves to true (allowed) or false (denied).
 *
 * Calls POST /permissions/check first. If already "always" granted,
 * resolves immediately. Otherwise shows the inline dialog.
 */
async function requestPermission(actionId, description) {
  try {
    const check = await fetch(`${BACKEND}/permissions/check`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ action_id: actionId, description }),
    }).then(r => r.json());

    if (check.granted && !check.needs_prompt) {
      return true; // already allowed always
    }
  } catch (_) {}

  // Show inline permission dialog in the chat
  return new Promise(resolve => {
    const list = $('messages');
    if (!list) { resolve(false); return; }

    const row = document.createElement('div');
    row.className = 'msg-row bot perm-dialog-row';

    const avatar = document.createElement('img');
    avatar.src = 'avatars/focused.svg';
    avatar.className = 'msg-avatar';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble perm-dialog-bubble';
    bubble.innerHTML = `
      <div class="perm-dialog-header">
        <span class="perm-lock">🔒</span>
        <strong>Permission Request</strong>
      </div>
      <p class="perm-dialog-desc">AuraBot wants to <strong>${escHtml(description)}</strong>.</p>
      <div class="perm-dialog-actions">
        <button class="perm-btn perm-once"   data-choice="once">Allow once</button>
        <button class="perm-btn perm-always" data-choice="always">Allow always</button>
        <button class="perm-btn perm-deny"   data-choice="deny">Deny</button>
      </div>
    `;

    row.appendChild(avatar);
    row.appendChild(bubble);
    list.appendChild(row);
    list.scrollTop = list.scrollHeight;

    AvatarController.setExpression('focused');

    async function handleChoice(choice) {
      // Disable all buttons
      bubble.querySelectorAll('.perm-btn').forEach(b => { b.disabled = true; });

      const granted = (choice !== 'deny');

      // Persist to backend if always or deny
      if (choice !== 'once') {
        try {
          await fetch(`${BACKEND}/permissions/grant`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ action_id: actionId, description, choice }),
          });
        } catch (_) {}
      }

      // Replace dialog bubble with result message
      const resultText = choice === 'always'
        ? `✓ Always allowed: ${description}`
        : choice === 'once'
        ? `✓ Allowed once: ${description}`
        : `✗ Denied: ${description}`;

      bubble.className = 'msg-bubble';
      bubble.textContent = resultText;
      bubble.style.opacity = '0.7';

      AvatarController.setExpression(granted ? 'happy' : 'idle');
      resolve(granted);
    }

    bubble.querySelectorAll('.perm-btn').forEach(btn => {
      btn.addEventListener('click', () => handleChoice(btn.dataset.choice));
    });
  });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Expose globally so other scripts (nudges, etc.) can use it
window.AuraBot = window.AuraBot || {};
window.AuraBot.requestPermission = requestPermission;

// ── Send button ────────────────────────────────────────────────────────────
function initSendBtn() {
  $('btn-send')?.addEventListener('click', sendMessage);
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  showScreen('loading');
  setStatus('Starting…', 'status-loading');

  initBackendEvents();
  initInputResize();
  initWindowControls();
  initFileAttach();
  initRetry();
  initSendBtn();
});
