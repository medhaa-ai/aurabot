'use strict';

const SettingsPanel = (() => {
  const BACKEND = 'http://127.0.0.1:8765';

  async function init() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => activateTab(btn.dataset.tab));
    });

    // Open / close
    document.getElementById('btn-tools').addEventListener('click', open);
    document.getElementById('settings-close').addEventListener('click', close);
    document.getElementById('settings-overlay').addEventListener('click', e => {
      if (e.target === e.currentTarget) close();
    });

    // Save handlers
    document.getElementById('btn-save-keys')?.addEventListener('click', saveKeys);
    document.getElementById('btn-save-profile')?.addEventListener('click', saveProfile);

    // Memory tab buttons (Phase 4)
    document.getElementById('btn-wipe-memory')?.addEventListener('click', wipeMemory);
    document.getElementById('btn-export-memory')?.addEventListener('click', exportMemory);
    document.getElementById('btn-mem-search')?.addEventListener('click', () => {
      const q = document.getElementById('mem-search')?.value.trim();
      if (q) searchMemory(q);
    });
    document.getElementById('mem-search')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const q = e.target.value.trim();
        if (q) searchMemory(q);
      }
    });

    // Dark mode toggle
    const darkToggle = document.getElementById('toggle-dark');
    if (darkToggle) {
      darkToggle.checked = document.documentElement.dataset.theme !== 'light';
      darkToggle.addEventListener('change', () => {
        const theme = darkToggle.checked ? 'dark' : 'light';
        document.documentElement.dataset.theme = theme;
        _saveSetting('theme', theme);
      });
    }

    // Always-on-top toggle
    const aotToggle = document.getElementById('toggle-aot');
    if (aotToggle && window.electronAPI) {
      aotToggle.checked = await window.electronAPI.getAlwaysOnTop();
      aotToggle.addEventListener('change', () => window.electronAPI.toggleAlwaysOnTop());
      window.electronAPI.onAlwaysOnTopChanged(val => { aotToggle.checked = val; });
    }

    // Pin button handled in app.js initWindowControls

    // Gmail + Calendar share one OAuth flow
    document.getElementById('btn-connect-gmail')?.addEventListener('click', connectGmail);
    document.getElementById('btn-disconnect-gmail')?.addEventListener('click', disconnectGmail);

    // WhatsApp buttons (Phase 6)
    document.getElementById('btn-start-wa')?.addEventListener('click', startWhatsApp);
    document.getElementById('btn-stop-wa')?.addEventListener('click', disconnectWhatsApp);

    await loadSettings();
    await refreshGmailStatus();    // check on open
    await refreshCalendarStatus(); // check on open
    await refreshWaStatus();       // check on open
  }

  // ── Tab management ─────────────────────────────────────────────────────

  function activateTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.tab === tabId));
    document.querySelectorAll('.tab-panel').forEach(p =>
      p.classList.toggle('active', p.id === `tab-${tabId}`));

    // Refresh live data when switching to these tabs
    if (tabId === 'permissions') renderPermissions();
    if (tabId === 'api-keys')    { refreshKeyStatus(); refreshGmailStatus(); refreshCalendarStatus(); refreshWaStatus(); }
    if (tabId === 'memory')      renderMemory();
  }

  // ── Open / close ──────────────────────────────────────────────────────

  function open() {
    const overlay = document.getElementById('settings-overlay');
    overlay.removeAttribute('hidden');
    refreshKeyStatus();
    refreshWaStatus();     // immediate refresh so status is never stale on open
    _startWaHeartbeat();   // keep refreshing every 5 s while panel is open
  }

  function close() {
    document.getElementById('settings-overlay').hidden = true;
    _stopWaHeartbeat();    // no need to poll when panel is closed
  }

  // ── Backend helpers ────────────────────────────────────────────────────

  async function _post(path, body) {
    const res = await fetch(`${BACKEND}${path}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    return res.json();
  }

  async function _get(path) {
    const res = await fetch(`${BACKEND}${path}`);
    return res.json();
  }

  async function _saveSetting(key, value) {
    try {
      await _post('/settings/set', { key, value: String(value) });
    } catch (_) {}
  }

  // ── Load settings → populate form fields ──────────────────────────────

  async function loadSettings() {
    try {
      const data = await _get('/settings/get');
      const set  = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };

      set('profile-name', data.user_name);
      set('profile-tz',   data.timezone);
      set('work-start',   data.work_start);
      set('work-end',     data.work_end);

      if (data.greeting_style) {
        const sel = document.getElementById('greeting-style');
        if (sel) sel.value = data.greeting_style;
      }
      if (data.theme) {
        document.documentElement.dataset.theme = data.theme;
        const dt = document.getElementById('toggle-dark');
        if (dt) dt.checked = data.theme !== 'light';
      }

      // Reflect key presence in the inputs
      _reflectKeyStatus(data);
    } catch (_) {}
  }

  // ── API Keys tab ───────────────────────────────────────────────────────

  async function refreshKeyStatus() {
    try {
      const status = await _get('/secrets/status');
      _reflectKeyStatus(status);
    } catch (_) {}
  }

  function _reflectKeyStatus(data) {
    const keyMap = {
      'key-anthropic':     data.has_anthropic_key     || data.anthropic_key,
      'key-serpapi':       data.has_serpapi_key        || data.serpapi_key,
      'key-google-id':     data.has_google_client_id   || data.google_client_id,
      'key-google-secret': data.has_google_client_secret || data.google_client_secret,
    };
    for (const [id, hasValue] of Object.entries(keyMap)) {
      const el = document.getElementById(id);
      if (!el) continue;
      if (hasValue && !el.value) {
        el.placeholder = '●●●●●●●● (saved)';
        el.dataset.saved = 'true';
      }
    }
  }

  async function saveKeys() {
    const fields = {
      anthropic_key:        document.getElementById('key-anthropic')?.value.trim(),
      serpapi_key:          document.getElementById('key-serpapi')?.value.trim(),
      google_client_id:     document.getElementById('key-google-id')?.value.trim(),
      google_client_secret: document.getElementById('key-google-secret')?.value.trim(),
    };

    let saved = 0;
    for (const [k, v] of Object.entries(fields)) {
      if (v) {
        try {
          await _post('/settings/set', { key: k, value: v });
          saved++;
        } catch (_) {}
      }
    }

    if (saved === 0) {
      showToast('Enter at least one key to save.');
      return;
    }

    // Clear the fields and update placeholders
    ['key-anthropic','key-serpapi','key-google-id','key-google-secret'].forEach(id => {
      const el = document.getElementById(id);
      if (el && el.value) {
        el.value = '';
        el.placeholder = '●●●●●●●● (saved)';
      }
    });

    showToast(`${saved} key${saved > 1 ? 's' : ''} saved (encrypted).`);
  }

  // ── Profile tab ────────────────────────────────────────────────────────

  async function saveProfile() {
    const fields = {
      user_name:      document.getElementById('profile-name')?.value.trim(),
      timezone:       document.getElementById('profile-tz')?.value.trim(),
      work_start:     document.getElementById('work-start')?.value,
      work_end:       document.getElementById('work-end')?.value,
      greeting_style: document.getElementById('greeting-style')?.value,
    };

    for (const [k, v] of Object.entries(fields)) {
      if (v !== undefined && v !== '') await _saveSetting(k, v);
    }
    showToast('Profile saved.');
  }

  // ── Permissions tab ────────────────────────────────────────────────────

  async function renderPermissions() {
    const container = document.getElementById('permissions-list');
    if (!container) return;

    container.innerHTML = '<p class="empty-state" style="padding:8px">Loading…</p>';

    try {
      const perms = await _get('/permissions/list');

      if (!perms || perms.length === 0) {
        container.innerHTML = '<p class="empty-state">No permissions granted yet.</p>';
        return;
      }

      container.innerHTML = perms.map(p => `
        <div class="perm-row" data-id="${escHtml(p.action_id)}">
          <div class="perm-info">
            <span class="perm-action">${escHtml(p.description || p.action_id)}</span>
            <span class="perm-choice perm-${p.choice}">${p.choice}</span>
          </div>
          <button class="btn-danger btn-sm perm-revoke-btn" data-id="${escHtml(p.action_id)}">
            Revoke
          </button>
        </div>
      `).join('');

      container.querySelectorAll('.perm-revoke-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.dataset.id;
          btn.textContent = '…';
          btn.disabled = true;
          try {
            await _post(`/permissions/revoke/${encodeURIComponent(id)}`, {});
            btn.closest('.perm-row').remove();
            if (!container.querySelector('.perm-row')) {
              container.innerHTML = '<p class="empty-state">No permissions granted yet.</p>';
            }
            showToast('Permission revoked.');
          } catch (_) {
            btn.textContent = 'Revoke';
            btn.disabled = false;
          }
        });
      });

    } catch (_) {
      container.innerHTML = '<p class="empty-state">Could not load permissions.</p>';
    }
  }

  // ── Gmail connect (Phase 5) ───────────────────────────────────────────

  let _gmailPollTimer = null;

  async function refreshGmailStatus() {
    try {
      const status = await _get('/gmail/status');
      _applyGmailStatus(status);
    } catch (_) {}
  }

  function _applyGmailStatus(status) {
    const badge      = document.getElementById('gmail-status-badge');
    const emailLabel = document.getElementById('gmail-email-label');
    const connectBtn = document.getElementById('btn-connect-gmail');
    const discBtn    = document.getElementById('btn-disconnect-gmail');
    const pollLabel  = document.getElementById('gmail-poll-label');

    if (status.connected) {
      if (badge)      { badge.textContent = 'Connected'; badge.className = 'gmail-badge gmail-badge-on'; }
      if (emailLabel) { emailLabel.textContent = status.email || ''; emailLabel.hidden = !status.email; }
      if (connectBtn) connectBtn.hidden = true;
      if (discBtn)    discBtn.hidden    = false;
      if (pollLabel)  pollLabel.hidden  = true;
      _stopGmailPoll();
    } else {
      if (badge)      { badge.textContent = 'Not connected'; badge.className = 'gmail-badge gmail-badge-off'; }
      if (emailLabel) emailLabel.hidden = true;
      if (connectBtn) connectBtn.hidden = false;
      if (discBtn)    discBtn.hidden    = true;
    }
  }

  async function connectGmail() {
    try {
      const data = await _get('/gmail/auth-url');
      if (!data.url) { showToast('Add Google Client ID + Secret first.'); return; }

      // Open the OAuth URL in the system browser
      if (window.electronAPI?.openExternal) {
        await window.electronAPI.openExternal(data.url);
      } else {
        window.open(data.url, '_blank');
      }

      // Show "waiting" label and start polling for connection
      const pollLabel = document.getElementById('gmail-poll-label');
      if (pollLabel) pollLabel.hidden = false;

      _startGmailPoll();
    } catch (err) {
      showToast(`Could not start Gmail auth: ${err.message}`);
    }
  }

  function _startGmailPoll() {
    _stopGmailPoll();
    let attempts = 0;
    _gmailPollTimer = setInterval(async () => {
      attempts++;
      try {
        const status = await _get('/gmail/status');
        if (status.connected) {
          _applyGmailStatus(status);
          refreshCalendarStatus();
          showToast('Google connected — Gmail & Calendar ready!');
          return;
        }
      } catch (_) {}
      if (attempts >= 60) {  // stop after ~2 minutes
        _stopGmailPoll();
        const pollLabel = document.getElementById('gmail-poll-label');
        if (pollLabel) pollLabel.hidden = true;
        showToast('Gmail authorisation timed out. Please try again.');
      }
    }, 2000);
  }

  function _stopGmailPoll() {
    if (_gmailPollTimer) { clearInterval(_gmailPollTimer); _gmailPollTimer = null; }
  }

  async function disconnectGmail() {
    if (!confirm('Disconnect Google? AuraBot will lose access to Gmail and Calendar.')) return;
    try {
      await _post('/gmail/disconnect', {});
      _applyGmailStatus({ connected: false, email: null });
      _applyCalendarStatus({ connected: false });
      showToast('Google disconnected.');
    } catch (_) {
      showToast('Disconnect failed — please try again.');
    }
  }

  // ── Calendar connect (Phase 7) ────────────────────────────────────────

  let _calPollTimer = null;

  async function refreshCalendarStatus() {
    try {
      const status = await _get('/calendar/status');
      _applyCalendarStatus(status);
    } catch (_) {}
  }

  function _applyCalendarStatus(status) {
    const badge    = document.getElementById('cal-status-badge');
    const connectB = document.getElementById('btn-connect-cal');
    const discB    = document.getElementById('btn-disconnect-cal');
    const pollLbl  = document.getElementById('cal-poll-label');

    if (status.connected) {
      if (badge)    { badge.textContent = 'Connected'; badge.className = 'gmail-badge gmail-badge-on'; }
      if (connectB) connectB.hidden = true;
      if (discB)    discB.hidden    = false;
      if (pollLbl)  pollLbl.hidden  = true;
      _stopCalPoll();
    } else {
      if (badge)    { badge.textContent = 'Not connected'; badge.className = 'gmail-badge gmail-badge-off'; }
      if (connectB) connectB.hidden = false;
      if (discB)    discB.hidden    = true;
    }
  }

  async function connectCalendar() {
    try {
      const data = await _get('/calendar/auth-url');
      if (!data.url) { showToast('Add Google Client ID + Secret first.'); return; }
      if (window.electronAPI?.openExternal) {
        await window.electronAPI.openExternal(data.url);
      } else {
        window.open(data.url, '_blank');
      }
      const pollLbl = document.getElementById('cal-poll-label');
      if (pollLbl) pollLbl.hidden = false;
      _startCalPoll();
    } catch (err) {
      showToast(`Could not start Calendar auth: ${err.message}`);
    }
  }

  function _startCalPoll() {
    _stopCalPoll();
    let attempts = 0;
    _calPollTimer = setInterval(async () => {
      attempts++;
      try {
        const status = await _get('/calendar/status');
        if (status.connected) {
          _applyCalendarStatus(status);
          refreshGmailStatus(); // may also now be connected
          showToast('Google Calendar connected!');
          return;
        }
      } catch (_) {}
      if (attempts >= 60) {
        _stopCalPoll();
        const pollLbl = document.getElementById('cal-poll-label');
        if (pollLbl) pollLbl.hidden = true;
        showToast('Calendar authorisation timed out. Please try again.');
      }
    }, 2000);
  }

  function _stopCalPoll() {
    if (_calPollTimer) { clearInterval(_calPollTimer); _calPollTimer = null; }
  }

  async function disconnectCalendar() {
    if (!confirm('Disconnect Calendar? This also disconnects Gmail (shared credentials).')) return;
    try {
      await _post('/gmail/disconnect', {});
      _applyCalendarStatus({ connected: false });
      _applyGmailStatus({ connected: false, email: null });
      showToast('Calendar (and Gmail) disconnected.');
    } catch (_) {
      showToast('Disconnect failed — please try again.');
    }
  }

  // ── WhatsApp connect (Phase 6) ────────────────────────────────────────

  let _waPollTimer = null;

  async function refreshWaStatus() {
    try {
      const status = await _get('/whatsapp/status');
      _applyWaStatus(status);
    } catch (_) {}
  }

  function _applyWaStatus(status) {
    const badge     = document.getElementById('wa-status-badge');
    const nameLabel = document.getElementById('wa-name-label');
    const startBtn  = document.getElementById('btn-start-wa');
    const stopBtn   = document.getElementById('btn-stop-wa');
    const pollLabel = document.getElementById('wa-poll-label');
    const qrWrap    = document.getElementById('wa-qr-wrap');

    if (status.connected) {
      if (badge)     { badge.textContent = 'Connected'; badge.className = 'wa-badge wa-badge-on'; }
      if (nameLabel) {
        nameLabel.textContent = status.name ? `Connected as: ${status.name}` : 'Connected';
        nameLabel.hidden = false;
      }
      if (startBtn)  startBtn.hidden = true;
      if (stopBtn)   stopBtn.hidden  = false;
      if (pollLabel) pollLabel.hidden = true;
      if (qrWrap)    qrWrap.hidden   = true;
      _stopWaPoll();
    } else if (status.bridge_running) {
      if (badge)     { badge.textContent = 'Scan QR'; badge.className = 'wa-badge wa-badge-off'; }
      if (nameLabel) nameLabel.hidden = true;
      if (startBtn)  startBtn.hidden = true;
      if (stopBtn)   stopBtn.hidden  = false;
      if (pollLabel) { pollLabel.textContent = 'Waiting for QR scan…'; pollLabel.hidden = false; }
      _updateWaQr();
    } else {
      if (badge)     { badge.textContent = 'Not running'; badge.className = 'wa-badge wa-badge-off'; }
      if (nameLabel) nameLabel.hidden = true;
      if (startBtn)  startBtn.hidden = false;
      if (stopBtn)   stopBtn.hidden  = true;
      if (pollLabel) pollLabel.hidden = true;
      if (qrWrap)    qrWrap.hidden   = true;
      _stopWaPoll();
    }
  }

  async function _updateWaQr() {
    try {
      const data   = await _get('/whatsapp/qr');
      const qrWrap = document.getElementById('wa-qr-wrap');
      const qrImg  = document.getElementById('wa-qr-img');
      if (data.qr && qrWrap && qrImg) {
        qrImg.src     = data.qr;
        qrWrap.hidden = false;
      } else if (qrWrap) {
        qrWrap.hidden = true;
      }
    } catch (_) {}
  }

  async function startWhatsApp() {
    const startBtn = document.getElementById('btn-start-wa');
    if (startBtn) { startBtn.disabled = true; startBtn.textContent = 'Starting…'; }
    try {
      const res = await _post('/whatsapp/start', {});
      if (res.message) showToast(res.message);
      await refreshWaStatus();
      _startWaPoll();
    } catch (err) {
      showToast(`Could not start WhatsApp: ${err.message}`);
    } finally {
      if (startBtn) { startBtn.disabled = false; startBtn.textContent = 'Start WhatsApp'; }
    }
  }

  function _startWaPoll() {
    _stopWaPoll();
    let attempts = 0;
    _waPollTimer = setInterval(async () => {
      attempts++;
      try {
        const status = await _get('/whatsapp/status');
        _applyWaStatus(status);   // always updates UI; stops poll if connected
        if (status.connected) {
          showToast('WhatsApp connected!');
          return;
        }
        if (status.bridge_running) await _updateWaQr();
      } catch (_) {}
      if (attempts >= 200) {    // ~10 min — long enough for slow session restore
        _stopWaPoll();
        showToast('WhatsApp scan timed out. Please try again.');
      }
    }, 3000);
  }

  // Lightweight background heartbeat — refreshes WA status every 5 s while
  // Settings is open, so the UI picks up a connected bridge automatically.
  let _waHeartbeatTimer = null;
  function _startWaHeartbeat() {
    if (_waHeartbeatTimer) return;
    _waHeartbeatTimer = setInterval(async () => {
      try {
        const status = await _get('/whatsapp/status');
        _applyWaStatus(status);
      } catch (_) {}
    }, 5000);
  }
  function _stopWaHeartbeat() {
    if (_waHeartbeatTimer) { clearInterval(_waHeartbeatTimer); _waHeartbeatTimer = null; }
  }

  function _stopWaPoll() {
    if (_waPollTimer) { clearInterval(_waPollTimer); _waPollTimer = null; }
  }

  async function disconnectWhatsApp() {
    if (!confirm('Stop WhatsApp? The bridge process will be stopped.')) return;
    try {
      await _post('/whatsapp/disconnect', {});
      _applyWaStatus({ bridge_running: false, connected: false, name: null });
      showToast('WhatsApp stopped.');
    } catch (_) {
      showToast('Stop failed — please try again.');
    }
  }

  // ── Memory tab (Phase 4) ──────────────────────────────────────────────

  async function renderMemory() {
    try {
      const stats = await _get('/memory/stats');
      const countEl = document.getElementById('mem-fact-count');
      const dateEl  = document.getElementById('mem-last-summary');
      if (countEl) countEl.textContent = stats.count ?? '—';
      if (dateEl)  dateEl.textContent  = stats.last_date ?? 'Never';
    } catch (_) {}
  }

  async function searchMemory(query) {
    const container = document.getElementById('mem-results');
    if (!container) return;
    container.innerHTML = '<p class="empty-state">Searching…</p>';
    try {
      const results = await _get(`/memory/search?q=${encodeURIComponent(query)}`);
      if (!results || results.length === 0) {
        container.innerHTML = '<p class="empty-state">No matching memories found.</p>';
        return;
      }
      container.innerHTML = results.map(r => {
        const meta = r.metadata || {};
        return `
          <div class="mem-result-row" data-id="${escHtml(r.id)}">
            <div class="mem-result-date">${escHtml(meta.date || '?')}</div>
            <div class="mem-result-text">
              <div class="mem-result-user">${escHtml((meta.user || '').slice(0, 120))}</div>
              <div class="mem-result-bot">${escHtml((meta.bot  || '').slice(0, 160))}</div>
            </div>
            <button class="btn-danger btn-sm mem-forget-btn" data-id="${escHtml(r.id)}">Forget</button>
          </div>
        `;
      }).join('');

      container.querySelectorAll('.mem-forget-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id  = btn.dataset.id;
          btn.textContent = '…';
          btn.disabled    = true;
          try {
            await _post('/memory/delete', { ids: [id] });
            btn.closest('.mem-result-row').remove();
            if (!container.querySelector('.mem-result-row')) {
              container.innerHTML = '<p class="empty-state">No matching memories found.</p>';
            }
            await renderMemory();
            showToast('Memory forgotten.');
          } catch (_) {
            btn.textContent = 'Forget';
            btn.disabled    = false;
          }
        });
      });
    } catch (_) {
      container.innerHTML = '<p class="empty-state">Search failed.</p>';
    }
  }

  async function wipeMemory() {
    if (!confirm('Wipe ALL memory? AuraBot will forget every past conversation. This cannot be undone.')) return;
    try {
      const res = await _post('/memory/wipe', {});
      document.getElementById('mem-results').innerHTML = '';
      await renderMemory();
      showToast(`Memory wiped (${res.deleted || 0} entries deleted).`);
    } catch (_) {
      showToast('Wipe failed — please try again.');
    }
  }

  async function exportMemory() {
    try {
      const data = await _get('/memory/export');
      if (!data || data.length === 0) {
        showToast('No memories to export yet.');
        return;
      }
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `aurabot_memory_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast(`Exported ${data.length} memory entries.`);
    } catch (_) {
      showToast('Export failed — please try again.');
    }
  }

  // ── Toast ──────────────────────────────────────────────────────────────

  function showToast(msg) {
    const t = document.createElement('div');
    t.textContent = msg;
    Object.assign(t.style, {
      position: 'fixed', bottom: '80px', left: '50%',
      transform: 'translateX(-50%)',
      background: 'var(--accent)', color: '#0F1729',
      padding: '8px 18px', borderRadius: '8px',
      fontSize: '0.85em', fontWeight: '600',
      zIndex: '9999', pointerEvents: 'none',
      opacity: '0', transition: 'opacity 0.2s',
      whiteSpace: 'nowrap',
    });
    document.body.appendChild(t);
    requestAnimationFrame(() => { t.style.opacity = '1'; });
    setTimeout(() => {
      t.style.opacity = '0';
      setTimeout(() => t.remove(), 200);
    }, 2200);
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { init, open, close, activateTab, renderPermissions, renderMemory, showToast, refreshWaStatus, refreshCalendarStatus };
})();

document.addEventListener('DOMContentLoaded', () => SettingsPanel.init());
