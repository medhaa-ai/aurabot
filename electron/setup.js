'use strict';

/**
 * AuraBot first-run environment setup.
 *
 * On first launch (or after a requirements change) creates a Python venv at
 * ~/.aurabot/venv/ and installs all backend dependencies.
 *
 * Called from electron/main.js before spawnPythonBackend().
 *
 * The venv is stored in the user's data directory so it survives app updates.
 * A SHA-256 hash of requirements.txt is stored alongside; if the hash changes
 * (new app version with new deps), setup re-runs automatically.
 */

const { app }      = require('electron');
const { execFile } = require('child_process');
const crypto       = require('crypto');
const fs           = require('fs');
const os           = require('os');
const path         = require('path');

const VENV_DIR    = path.join(os.homedir(), '.aurabot', 'venv');
const HASH_FILE   = path.join(os.homedir(), '.aurabot', 'req_hash.txt');


// ── Path helpers ───────────────────────────────────────────────────────────

function getVenvPython() {
  return process.platform === 'win32'
    ? path.join(VENV_DIR, 'Scripts', 'python.exe')
    : path.join(VENV_DIR, 'bin',     'python');
}

function getVenvPip() {
  return process.platform === 'win32'
    ? path.join(VENV_DIR, 'Scripts', 'pip.exe')
    : path.join(VENV_DIR, 'bin',     'pip');
}

function getSystemPython() {
  return process.platform === 'win32' ? 'python' : 'python3';
}

function getRequirementsPath() {
  if (app.isPackaged) {
    // In packaged app, files land in resources/app/ (asar: false)
    return path.join(process.resourcesPath, 'app', 'requirements.txt');
  }
  return path.join(__dirname, '..', 'requirements.txt');
}

function getBackendScript() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'app', 'backend', 'main.py');
  }
  return path.join(__dirname, '..', 'backend', 'main.py');
}

function getBridgeDir() {
  if (app.isPackaged) {
    // electron-builder puts whatsapp_bridge in resources/ via extraResources
    return path.join(process.resourcesPath, 'whatsapp_bridge');
  }
  return path.join(__dirname, '..', 'whatsapp_bridge');
}


// ── Helpers ────────────────────────────────────────────────────────────────

function run(cmd, args, onProgress) {
  return new Promise((resolve, reject) => {
    const child = execFile(cmd, args, { maxBuffer: 50 * 1024 * 1024 });
    child.stdout?.on('data', d => onProgress?.(String(d).trim()));
    child.stderr?.on('data', d => onProgress?.(String(d).trim()));
    child.on('close',  code  => code === 0 ? resolve() : reject(new Error(`Process exited with code ${code}`)));
    child.on('error',  reject);
  });
}

function reqHash() {
  const reqPath = getRequirementsPath();
  if (!fs.existsSync(reqPath)) return '';
  const content = fs.readFileSync(reqPath, 'utf8');
  return crypto.createHash('sha256').update(content).digest('hex').slice(0, 16);
}

function savedHash() {
  try { return fs.readFileSync(HASH_FILE, 'utf8').trim(); } catch (_) { return ''; }
}


// ── Helpers ────────────────────────────────────────────────────────────────

async function _ensureBridge(notify) {
  const bridgeDir     = getBridgeDir();
  const bridgeModules = path.join(bridgeDir, 'node_modules');
  if (fs.existsSync(bridgeDir) && !fs.existsSync(bridgeModules)) {
    notify('Installing WhatsApp bridge dependencies…');
    try {
      await run('npm', ['install', '--prefix', bridgeDir, '--silent'], notify);
    } catch (e) {
      console.warn('[setup] WhatsApp bridge install failed (non-fatal):', e.message);
    }
  }
}


// ── Public API ─────────────────────────────────────────────────────────────

/**
 * Ensure the Python venv exists and requirements are installed.
 * @param {function} onProgress  — callback(message: string)
 */
async function checkAndSetup(onProgress) {
  const notify = msg => {
    console.log('[setup]', msg);
    onProgress?.(msg);
  };

  const venvPython = getVenvPython();
  const currentHash = reqHash();
  const alreadySetUp = fs.existsSync(venvPython) && savedHash() === currentHash;

  if (alreadySetUp) {
    notify('Python environment ready.');
    // Still check bridge even when Python env is cached
    await _ensureBridge(notify);
    return;
  }

  // ── Create venv ──────────────────────────────────────────────────────────
  if (!fs.existsSync(venvPython)) {
    notify('Creating Python environment (first run — one moment)…');
    try {
      await run(getSystemPython(), ['-m', 'venv', VENV_DIR], notify);
    } catch (e) {
      throw new Error(
        `Could not create Python virtual environment: ${e.message}\n` +
        `Make sure Python 3.10+ is installed and on your PATH.\n` +
        `Download from https://www.python.org/downloads/`
      );
    }
  }

  // ── Install requirements ─────────────────────────────────────────────────
  notify('Installing Python packages — this takes 2-3 minutes on first run…');
  const reqPath = getRequirementsPath();
  if (!fs.existsSync(reqPath)) {
    throw new Error(`requirements.txt not found at ${reqPath}`);
  }

  try {
    await run(getVenvPip(), ['install', '-r', reqPath, '--quiet', '--no-warn-script-location'], notify);
  } catch (e) {
    throw new Error(`Package installation failed: ${e.message}`);
  }

  // ── WhatsApp bridge npm install ──────────────────────────────────────────
  await _ensureBridge(notify);

  // ── Save hash so we skip setup next time ─────────────────────────────────
  fs.writeFileSync(HASH_FILE, currentHash, 'utf8');
  notify('Setup complete!');
}

module.exports = { checkAndSetup, getVenvPython, getBackendScript, getBridgeDir };
