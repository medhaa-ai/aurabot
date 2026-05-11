'use strict';

const { spawn }   = require('child_process');
const { app }     = require('electron');
const { getVenvPython, getBackendScript } = require('./setup');
const path = require('path');
const fs   = require('fs');
const os   = require('os');
const http = require('http');

let pythonProcess = null;
const BACKEND_PORT = 8765;
const HEALTH_URL   = `http://127.0.0.1:${BACKEND_PORT}/health`;


function getPythonExecutable() {
  // 1. In packaged mode: use ~/.aurabot/venv/ (created by setup.js)
  if (app.isPackaged) {
    const venvPy = getVenvPython();
    if (fs.existsSync(venvPy)) return venvPy;
    // Fallback to system Python (user may have cancelled setup)
    return process.platform === 'win32' ? 'python' : 'python3';
  }

  // 2. Development: try venv relative to project root
  const candidates = [
    path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe'),
    path.join(__dirname, '..', 'venv', 'bin',     'python'),
    path.join(__dirname, '..', '.venv','Scripts',  'python.exe'),
    path.join(__dirname, '..', '.venv','bin',      'python'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function getScript() {
  return getBackendScript();
}

function checkHealth() {
  return new Promise(resolve => {
    const req = http.get(HEALTH_URL, { timeout: 800 }, res => {
      resolve(res.statusCode === 200);
    });
    req.on('error',   () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function waitForHealth(maxWaitMs = 30000, intervalMs = 1000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + maxWaitMs;

    async function attempt() {
      const ok = await checkHealth();
      if (ok) return resolve();
      if (Date.now() >= deadline) {
        return reject(new Error(
          `AuraBot backend did not start within ${maxWaitMs / 1000}s. ` +
          `Check ${path.join(os.homedir(), '.aurabot', 'logs', 'backend.log')} for details.`
        ));
      }
      setTimeout(attempt, intervalMs);
    }

    setTimeout(attempt, 800);
  });
}

async function spawnPythonBackend() {
  const python = getPythonExecutable();
  const script = getScript();
  const logDir = path.join(os.homedir(), '.aurabot', 'logs');
  fs.mkdirSync(logDir, { recursive: true });

  const logFd = fs.openSync(path.join(logDir, 'backend.log'), 'a');

  // Compute project root for PYTHONPATH so `from backend.X import Y` works
  const projectRoot = app.isPackaged
    ? path.join(process.resourcesPath, 'app')
    : path.join(__dirname, '..');

  pythonProcess = spawn(python, [script], {
    stdio: ['ignore', logFd, logFd],
    env:   { ...process.env, PYTHONPATH: projectRoot },
    detached: false,
  });

  pythonProcess.on('error', err => {
    console.error('[python_spawner] spawn error:', err.message);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`[python_spawner] backend exited — code=${code} signal=${signal}`);
    pythonProcess = null;
  });

  await waitForHealth();
  console.log('[python_spawner] backend healthy on port', BACKEND_PORT);
  return pythonProcess;
}

function killPythonBackend() {
  if (!pythonProcess) return;
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t'], { stdio: 'ignore' });
    } else {
      pythonProcess.kill('SIGTERM');
    }
  } catch (_) {}
  pythonProcess = null;
}

module.exports = { spawnPythonBackend, killPythonBackend };
