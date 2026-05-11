"""Phase 1 self-test — runs against the live backend on 127.0.0.1:8765.

Usage:
  # With the app running (npm start), open a second terminal and:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python -m pytest backend/tests/test_phase1.py -v
"""

import urllib.request
import json
import sys
import time

BASE = "http://127.0.0.1:8765"
TIMEOUT = 5


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _post(path: str, body: dict) -> dict:
    data  = json.dumps(body).encode()
    req   = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _post_sse(path: str, body: dict) -> list[dict]:
    """POST and parse SSE events (for /chat which streams in Phase 3+)."""
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", errors="replace")
    events = []
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            try:
                events.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                pass
    return events


# ── Tests ──────────────────────────────────────────────────────────────────

def test_health():
    """Backend must respond to /health with status=ok."""
    data = _get("/health")
    assert data.get("status") == "ok", f"Unexpected health response: {data}"
    print("  PASS health check")


def test_echo():
    """POST /chat must return an SSE stream with at least one chunk and a done event."""
    events = _post_sse("/chat", {"message": "hello"})
    types  = [e.get("type") for e in events]
    assert "done" in types, f"No 'done' event in SSE stream. Events: {types}"
    # Collect all text chunks
    text = "".join(e.get("text", "") for e in events if e.get("type") == "chunk")
    print(f"  PASS /chat SSE: {len(events)} event(s), text starts: {text[:40]!r}")


def test_settings_get():
    """GET /settings/get must return a dict with user_name."""
    data = _get("/settings/get")
    assert isinstance(data, dict),         f"Expected dict, got: {type(data)}"
    assert "user_name" in data,            f"No 'user_name' in settings: {data}"
    print(f"  PASS settings get: user_name={data['user_name']!r}")


def test_settings_set():
    """POST /settings/set must persist a value retrievable via /settings/get."""
    _post("/settings/set", {"key": "test_phase1_key", "value": "phase1_value"})
    data = _get("/settings/get")
    assert data.get("test_phase1_key") == "phase1_value", \
        f"Setting not persisted. Got: {data.get('test_phase1_key')!r}"
    print("  PASS settings set/get round-trip")


def test_permissions_list():
    """GET /permissions/list must return a list."""
    data = _get("/permissions/list")
    assert isinstance(data, list), f"Expected list, got: {type(data)}"
    print(f"  PASS permissions list ({len(data)} items)")


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [test_health, test_echo, test_settings_get, test_settings_set, test_permissions_list]
    failures = []

    print("\n=== AuraBot Phase 1 Self-Test ===\n")

    # Wait for backend
    print("Waiting for backend…")
    for attempt in range(20):
        try:
            _get("/health")
            break
        except Exception:
            time.sleep(1)
    else:
        print("FAIL: Backend not reachable on 127.0.0.1:8765 after 20s")
        print("Make sure the app is running (npm start) then re-run this script.")
        sys.exit(1)

    print("Backend is up. Running tests…\n")

    for t in tests:
        try:
            t()
        except AssertionError as err:
            print(f"  FAIL {t.__name__}: {err}")
            failures.append(t.__name__)
        except Exception as err:
            print(f"  ERROR {t.__name__}: {err}")
            failures.append(t.__name__)

    print()
    if failures:
        print(f"RESULT: {len(failures)}/{len(tests)} tests FAILED: {', '.join(failures)}")
        sys.exit(1)
    else:
        print(f"RESULT: All {len(tests)} tests passed. Phase 1 is complete!")
        sys.exit(0)


if __name__ == "__main__":
    run_all()


# pytest-compatible wrappers (if running via pytest)
def test_via_pytest_health():       test_health()
def test_via_pytest_echo():         test_echo()
def test_via_pytest_settings_get(): test_settings_get()
def test_via_pytest_settings_set(): test_settings_set()
def test_via_pytest_permissions():  test_permissions_list()
