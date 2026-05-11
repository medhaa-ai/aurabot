#!/usr/bin/env node
/**
 * AuraBot launcher — removes ELECTRON_RUN_AS_NODE before spawning Electron.
 * Required because some parent processes (e.g. VS Code / Claude Code) set
 * ELECTRON_RUN_AS_NODE=1, which makes Electron behave as plain Node.js and
 * disables all Electron APIs including require('electron').app.
 */

const { spawn } = require('child_process');
const path = require('path');
const fs   = require('fs');

const electronExe = require('electron'); // returns path to binary from npm pkg

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;   // critical: must be absent, not "0"
delete env.ELECTRON_NO_ASAR;       // just in case

const appDir = path.join(__dirname);

const child = spawn(electronExe, [appDir], {
  env,
  stdio: 'inherit',
  windowsHide: false,
});

child.on('exit', code => process.exit(code ?? 0));
child.on('error', err => { console.error('Failed to launch Electron:', err.message); process.exit(1); });
