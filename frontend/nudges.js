'use strict';

// Nudges panel — collapsible list of urgent items (Phase 7: server polling)
const NudgesPanel = (() => {
  const BACKEND = 'http://127.0.0.1:8765';

  let toggleBtn  = null;
  let listEl     = null;
  let countEl    = null;
  let items      = [];
  let expanded   = false;
  let _pollTimer = null;
  const _seenIds = new Set();

  function init() {
    toggleBtn = document.getElementById('nudges-toggle');
    listEl    = document.getElementById('nudges-list');
    countEl   = document.getElementById('nudge-count');

    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggle);
    }
    render();
  }

  function toggle() {
    expanded = !expanded;
    listEl.classList.toggle('collapsed', !expanded);
    toggleBtn.setAttribute('aria-expanded', String(expanded));
  }

  function addItem({ id, text, urgency = 'low', sender = null }) {
    if (items.find(i => i.id === id)) return;
    items.push({ id, text, urgency, sender, ts: Date.now() });
    render();
    if (urgency === 'high' && !expanded) toggle();
  }

  async function removeItem(id) {
    items = items.filter(i => i.id !== id);
    render();
    try {
      await fetch(`${BACKEND}/nudges/dismiss`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ id }),
      });
    } catch (_) {}
  }

  function render() {
    if (!listEl) return;

    if (items.length === 0) {
      listEl.innerHTML = '<p class="nudge-empty">No active nudges — you\'re on top of things.</p>';
      if (countEl) countEl.hidden = true;
      return;
    }

    listEl.innerHTML = items.map(item => `
      <div class="nudge-item" data-id="${item.id}">
        <span class="nudge-urgency ${item.urgency}" title="Priority: ${item.urgency}"></span>
        <span class="nudge-text">${item.sender ? `<strong>${escHtml(item.sender)}:</strong> ` : ''}${escHtml(item.text)}</span>
        <button class="icon-btn nudge-dismiss" onclick="NudgesPanel.removeItem('${item.id}')" title="Dismiss" style="width:24px;height:24px;font-size:12px;border:none;background:transparent;">✕</button>
      </div>
    `).join('');

    if (countEl) {
      countEl.textContent = items.length;
      countEl.hidden = false;
    }
  }

  // ── Server polling (Phase 7) ───────────────────────────────────────────

  function startPolling() {
    if (_pollTimer) return;
    _pollServer(); // immediate first check
    _pollTimer = setInterval(_pollServer, 30000);
  }

  async function _pollServer() {
    try {
      const res  = await fetch(`${BACKEND}/nudges/pending`);
      const list = await res.json();
      if (!Array.isArray(list)) return;
      for (const n of list) {
        if (_seenIds.has(n.id)) continue;
        _seenIds.add(n.id);
        addItem({ id: n.id, text: n.text, urgency: n.urgency || 'low' });
      }
    } catch (_) {}
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;');
  }

  return { init, addItem, removeItem, toggle, startPolling };
})();

document.addEventListener('DOMContentLoaded', () => NudgesPanel.init());
