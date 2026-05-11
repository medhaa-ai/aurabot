/**
 * AuraBot end-to-end smoke test.
 *
 * Verifies the backend is reachable and all key endpoints respond correctly.
 * Run with the app already started (npm start).
 *
 * Usage:
 *   node tests_e2e/smoke.test.js
 */

'use strict';

const http = require('http');

const BASE    = 'http://127.0.0.1:8765';
const TIMEOUT = 10000;

let passed = 0;
let failed = 0;

// ── Helpers ──────────────────────────────────────────────────────────────────

function get(path) {
  return new Promise((resolve, reject) => {
    const req = http.get(`${BASE}${path}`, { timeout: TIMEOUT }, (res) => {
      let body = '';
      res.on('data', d => { body += d; });
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(body) }); }
        catch { resolve({ status: res.statusCode, body }); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error(`Timeout on ${path}`)); });
  });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function test(name, fn) {
  try {
    await fn();
    console.log(`  PASS  ${name}`);
    passed++;
  } catch (err) {
    console.log(`  FAIL  ${name}: ${err.message}`);
    failed++;
  }
}

// ── Tests ────────────────────────────────────────────────────────────────────

async function run() {
  console.log('\n=== AuraBot E2E Smoke Tests ===\n');

  // Wait up to 30s for backend
  let ready = false;
  for (let i = 0; i < 30; i++) {
    try { await get('/health'); ready = true; break; }
    catch { await new Promise(r => setTimeout(r, 1000)); }
  }
  if (!ready) {
    console.log('FAIL: Backend not reachable on http://127.0.0.1:8765');
    console.log('      Start the app with: npm start');
    process.exit(1);
  }

  await test('GET /health returns ok + version', async () => {
    const { body } = await get('/health');
    assert(body.status === 'ok', `Expected status "ok", got ${body.status}`);
    assert(body.version, 'Missing version field');
  });

  await test('GET /secrets/status returns key map', async () => {
    const { body } = await get('/secrets/status');
    assert(typeof body === 'object', 'Expected object');
    assert('anthropic_key' in body, 'Missing anthropic_key field');
  });

  await test('GET /gmail/status returns connected field', async () => {
    const { body } = await get('/gmail/status');
    assert(typeof body.connected === 'boolean', 'Expected boolean connected field');
  });

  await test('GET /calendar/status returns connected field', async () => {
    const { body } = await get('/calendar/status');
    assert(typeof body.connected === 'boolean', 'Expected boolean connected field');
  });

  await test('GET /whatsapp/status returns connected field', async () => {
    const { body } = await get('/whatsapp/status');
    assert(typeof body.connected === 'boolean', 'Expected boolean connected field');
  });

  await test('GET /memory/stats returns count', async () => {
    const { body } = await get('/memory/stats');
    assert(typeof body.count === 'number', 'Expected numeric count field');
  });

  await test('GET /reminders/list returns array', async () => {
    const { body } = await get('/reminders/list');
    assert(Array.isArray(body), 'Expected array');
  });

  await test('GET /nudges/pending returns array', async () => {
    const { body } = await get('/nudges/pending');
    assert(Array.isArray(body), 'Expected array');
  });

  await test('GET /settings/get returns object', async () => {
    const { body } = await get('/settings/get');
    assert(typeof body === 'object', 'Expected object');
  });

  await test('GET /permissions/list returns array', async () => {
    const { body } = await get('/permissions/list');
    assert(Array.isArray(body), 'Expected array');
  });

  // ── Summary ────────────────────────────────────────────────────────────────
  console.log('');
  if (failed === 0) {
    console.log(`RESULT: All ${passed} smoke tests passed.`);
    process.exit(0);
  } else {
    console.log(`RESULT: ${failed} of ${passed + failed} tests FAILED.`);
    process.exit(1);
  }
}

run();
