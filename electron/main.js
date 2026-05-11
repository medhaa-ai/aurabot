const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawnPythonBackend, killPythonBackend } = require('./python_spawner');
const { checkAndSetup } = require('./setup');

let mainWindow    = null;
let tray          = null;
let isQuitting    = false;
let isCompact     = false;
let expandedHeight = 620;
const windowStatePath = path.join(os.homedir(), '.aurabot', 'window_state.json');

function loadWindowState() {
  try {
    if (fs.existsSync(windowStatePath)) {
      const state = JSON.parse(fs.readFileSync(windowStatePath, 'utf8'));
      // Never restore a compact-mode height — always open fully expanded
      if (!state.height || state.height < 500) state.height = 620;
      return state;
    }
  } catch (_) {}
  return { width: 380, height: 620 };
}

function saveWindowState() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  try {
    const bounds = mainWindow.getBounds();
    // Save the expanded height even if currently collapsed
    if (isCompact) bounds.height = expandedHeight;
    fs.writeFileSync(windowStatePath, JSON.stringify(bounds));
  } catch (_) {}
}

async function createWindow() {
  const state = loadWindowState();
  const display = screen.getPrimaryDisplay();
  const { width: sw, height: sh } = display.workAreaSize;

  // Clamp saved position inside current screen
  let startX = state.x !== undefined ? state.x : Math.round((sw - 380) / 2);
  let startY = state.y !== undefined ? state.y : Math.round((sh - 620) / 4);
  startX = Math.max(0, Math.min(startX, sw - 320));
  startY = Math.max(0, Math.min(startY, sh - 200));

  mainWindow = new BrowserWindow({
    width: state.width || 380,
    height: state.height || 620,
    x: startX,
    y: startY,
    minWidth: 320,
    minHeight: 500,
    frame: false,
    transparent: false,
    backgroundColor: '#0F1729',
    roundedCorners: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
    resizable: true,
  });

  mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'index.html'));

  // Snap-to-edge after user finishes dragging
  mainWindow.on('moved', () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const { x, y, width, height } = mainWindow.getBounds();
    const { width: sw2, height: sh2 } = screen.getPrimaryDisplay().workAreaSize;
    const snap = 20;
    let nx = x, ny = y;
    if (x < snap) nx = 0;
    if (y < snap) ny = 0;
    if (x + width > sw2 - snap) nx = sw2 - width;
    if (y + height > sh2 - snap) ny = sh2 - height;
    if (nx !== x || ny !== y) mainWindow.setPosition(nx, ny);
    saveWindowState();
  });

  mainWindow.on('resized', saveWindowState);

  // Hide to tray on close instead of quitting
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
      tray?.displayBalloon?.({
        title: 'AuraBot',
        content: 'AuraBot is still running. Click the tray icon to bring it back.',
        iconType: 'info',
      });
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Show window immediately (loading screen is shown in HTML)
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  return mainWindow;
}

function createTrayIcon() {
  // Build a minimal 16×16 PNG tray icon from an inline base64 image
  // (a simplified "A" logo in the AuraBot accent color)
  const iconPath = path.join(__dirname, '..', 'frontend', 'icons', 'tray.png');

  let icon;
  if (fs.existsSync(iconPath)) {
    icon = nativeImage.createFromPath(iconPath);
  } else {
    // Fallback: tiny 1-pixel transparent PNG (tray will still show up on Windows)
    icon = nativeImage.createEmpty();
  }

  tray = new Tray(icon);
  tray.setToolTip('AuraBot');

  const menu = Menu.buildFromTemplate([
    {
      label: 'Show AuraBot',
      click: () => {
        if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        saveWindowState();
        killPythonBackend();
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(menu);

  // Single click shows the window
  tray.on('click', () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible()) {
      mainWindow.focus();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

app.whenReady().then(async () => {
  // Ensure ~/.aurabot directory tree exists
  const dirs = [
    path.join(os.homedir(), '.aurabot'),
    path.join(os.homedir(), '.aurabot', 'logs'),
    path.join(os.homedir(), '.aurabot', 'memory'),
  ];
  dirs.forEach(d => fs.mkdirSync(d, { recursive: true }));

  const win = await createWindow();
  createTrayIcon();

  // First-run setup (creates venv + installs deps if needed), then start Python backend
  try {
    await checkAndSetup(msg => {
      if (win && !win.isDestroyed()) {
        win.webContents.send('loading-status', msg);
      }
    });
    await spawnPythonBackend();
    if (win && !win.isDestroyed()) {
      win.webContents.send('backend-ready');
    }
  } catch (err) {
    console.error('Backend failed to start:', err.message);
    if (win && !win.isDestroyed()) {
      win.webContents.send('backend-error', err.message);
    }
  }
});

app.on('window-all-closed', () => {
  // Don't quit — tray keeps the app alive
  // Real quit only happens via tray "Quit" menu item
});

app.on('will-quit', () => {
  isQuitting = true;
  saveWindowState();
  killPythonBackend();
});

// ── IPC handlers ──────────────────────────────────────────────────────────────

ipcMain.on('window-minimize', () => mainWindow?.minimize());

ipcMain.on('window-toggle-compact', () => {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  const bounds  = mainWindow.getBounds();
  const HEADER_H = 64;

  if (isCompact) {
    mainWindow.setMinimumSize(320, 500);
    mainWindow.setResizable(true);
    mainWindow.setBounds({ x: bounds.x, y: bounds.y, width: bounds.width, height: expandedHeight });
    isCompact = false;
  } else {
    expandedHeight = bounds.height;
    mainWindow.setMinimumSize(320, HEADER_H);
    mainWindow.setResizable(false);
    mainWindow.setBounds({ x: bounds.x, y: bounds.y, width: bounds.width, height: HEADER_H });
    isCompact = true;
  }
  mainWindow.webContents.send('compact-changed', isCompact);
});

ipcMain.on('window-close', () => mainWindow?.hide()); // hides to tray, doesn't quit

ipcMain.on('window-toggle-always-on-top', () => {
  if (!mainWindow) return;
  const next = !mainWindow.isAlwaysOnTop();
  mainWindow.setAlwaysOnTop(next);
  mainWindow.webContents.send('always-on-top-changed', next);
});

ipcMain.handle('get-platform', () => process.platform);

ipcMain.handle('get-window-always-on-top', () => mainWindow?.isAlwaysOnTop() ?? false);

ipcMain.handle('open-external', (_event, url) => {
  // Only allow http/https URLs to prevent abuse
  if (/^https?:\/\//.test(url)) shell.openExternal(url);
});
