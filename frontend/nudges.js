'use strict';

// Nudges panel — collapsible list of urgent items (Phase 7: server polling)
const NudgesPanel = (() => {
  const BACKEND = 'http://127.0.0.1:8765';

  let toggleBtn       = null;
  let listEl          = null;
  let countEl         = null;
  let compactBadgeEl  = null;
  let items           = [];
  let expanded        = false;
  let _pollTimer      = null;
  const _seenIds      = new Set();

  function init() {
    toggleBtn      = document.getElementById('nudges-toggle');
    listEl         = document.getElementById('nudges-list');
    countEl        = document.getElementById('nudge-count');
    compactBadgeEl = document.getElementById('compact-nudge-badge');

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

  function addItem({ id, text, urgency = 'low', nudgeType = null }) {
    if (items.find(i => i.id === id)) return;
    items.push({ id, text, urgency, nudgeType, ts: Date.now() });
    render();

    if (urgency === 'high') {
      if (!expanded) toggle();
      _fireOsNotification(text, nudgeType, urgency);
    }
  }

  function _fireOsNotification(text, nudgeType, urgency) {
    try {
      const title = nudgeType === 'whatsapp'
        ? '💬 WhatsApp — Unread Messages'
        : '🔔 AuraBot Nudge';
      if (window.electronAPI?.showNotification) {
        window.electronAPI.showNotification(title, text, urgency);
      }
    } catch (_) {}
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

    // Update compact-mode badge
    if (compactBadgeEl) {
      const high = items.filter(i => i.urgency === 'high').length;
      compactBadgeEl.textContent  = items.length;
      compactBadgeEl.hidden       = items.length === 0;
      compactBadgeEl.className    = `compact-nudge-badge${high > 0 ? ' has-high' : ''}`;
    }

    if (items.length === 0) {
      listEl.innerHTML = '<p class="nudge-empty">No active nudges — you\'re on top of things.</p>';
      if (countEl) countEl.hidden = true;
      return;
    }

    listEl.innerHTML = items.map(item => {
      const typeClass = item.nudgeType ? ` nudge-type-${escHtml(item.nudgeType)}` : '';
      const urgClass  = ` urgency-${escHtml(item.urgency)}`;
      const icon      = item.nudgeType === 'whatsapp' ? '💬' : (item.urgency === 'high' ? '⚠️' : '');
      return `
        <div class="nudge-item${urgClass}${typeClass}" data-id="${item.id}">
          <span class="nudge-urgency ${item.urgency}" title="Priority: ${item.urgency}"></span>
          <span class="nudge-text">${icon ? `<span class="nudge-icon-inline">${icon}</span> ` : ''}${escHtml(item.text)}</span>
          <button class="nudge-dismiss" onclick="NudgesPanel.removeItem('${item.id}')" title="Dismiss">✕</button>
        </div>`;
    }).join('');

    if (countEl) {
      countEl.textContent = items.length;
      countEl.hidden = false;
    }
  }

  // ── Server polling ───────────────────────────────────────────────────────

  function startPolling() {
    if (_pollTimer) return;
    _pollServer();
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
        addItem({ id: n.id, text: n.text, urgency: n.urgency || 'low', nudgeType: n.nudge_type || null });
      }
    } catch (_) {}
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { init, addItem, removeItem, toggle, startPolling };
})();

document.addEventListener('DOMContentLoaded', () => NudgesPanel.init());
