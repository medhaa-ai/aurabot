const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  close: () => ipcRenderer.send('window-close'),
  toggleAlwaysOnTop: () => ipcRenderer.send('window-toggle-always-on-top'),
  getAlwaysOnTop: () => ipcRenderer.invoke('get-window-always-on-top'),
  toggleCompact: () => ipcRenderer.send('window-toggle-compact'),
  onCompactChanged: (cb) => ipcRenderer.on('compact-changed', (_e, val) => cb(val)),

  // Platform info
  getPlatform: () => ipcRenderer.invoke('get-platform'),

  // Backend lifecycle events (renderer listens)
  onBackendReady:       (cb) => ipcRenderer.on('backend-ready',       () => cb()),
  onBackendError:       (cb) => ipcRenderer.on('backend-error',       (_e, msg) => cb(msg)),
  onLoadingStatus:      (cb) => ipcRenderer.on('loading-status',      (_e, msg) => cb(msg)),
  onAlwaysOnTopChanged: (cb) => ipcRenderer.on('always-on-top-changed', (_e, val) => cb(val)),

  // Open a URL in the system default browser (used for OAuth flows)
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // OS-level toast notification
  showNotification: (title, body, urgency) =>
    ipcRenderer.send('show-notification', { title, body, urgency }),
});
