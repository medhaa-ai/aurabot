"""Phase 7 self-test — reminders, nudges, scheduler, calendar.

Tests run against the live backend on 127.0.0.1:8765.
Calendar tests that need a connected account are skipped automatically.

Usage:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python backend\\tests\\test_phase7.py
"""

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

BASE    = "http://127.0.0.1:8765"
TIMEOUT = 10


def _get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _post(path, body=None):
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _delete(path):
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


# ── Reminder tests ─────────────────────────────────────────────────────────

def test_reminder_add_and_list():
    """POST /reminders/add and GET /reminders/list must work."""
    fire_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    result  = _post("/reminders/add", {"text": "Test reminder", "fire_at": fire_at})
    assert result.get("ok") is True, f"Expected ok=True: {result}"
    rid = result.get("id")
    assert rid, f"Expected an id: {result}"

    reminders = _get("/reminders/list")
    assert isinstance(reminders, list), f"Expected list: {reminders}"
    ids = [r["id"] for r in reminders]
    assert rid in ids, f"Reminder {rid} not in list: {ids}"

    # Clean up
    _delete(f"/reminders/{rid}")
    print(f"  PASS POST /reminders/add + GET /reminders/list (id={rid})")


def test_reminder_delete():
    """POST /reminders/add then DELETE /reminders/{{id}} must remove it."""
    fire_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    result  = _post("/reminders/add", {"text": "Delete me", "fire_at": fire_at})
    rid     = result["id"]

    del_result = _delete(f"/reminders/{rid}")
    assert del_result.get("found") is True, f"Expected found=True: {del_result}"

    reminders = _get("/reminders/list")
    assert rid not in [r["id"] for r in reminders], f"Reminder {rid} still in list"
    print(f"  PASS DELETE /reminders/{{id}} (id={rid})")


def test_nudge_fired_for_past_reminder():
    """A reminder with fire_at in the past must appear in /nudges/pending."""
    # Dismiss any existing nudges first
    _post("/nudges/dismiss-all", {})

    fire_at = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    result  = _post("/reminders/add", {"text": "Past reminder test", "fire_at": fire_at})
    rid     = result["id"]

    # GET /nudges/pending triggers check_and_fire
    nudges = _get("/nudges/pending")
    assert isinstance(nudges, list), f"Expected list: {nudges}"
    texts = [n.get("text", "") for n in nudges]
    assert any("Past reminder test" in t for t in texts), \
        f"Expected nudge for past reminder, got: {texts}"
    print(f"  PASS Past reminder fires as nudge (id={rid})")

    # Clean up
    _post("/nudges/dismiss-all", {})


def test_nudge_dismiss():
    """POST /nudges/dismiss must remove a specific nudge."""
    _post("/nudges/dismiss-all", {})

    fire_at = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    _post("/reminders/add", {"text": "Dismiss test", "fire_at": fire_at})

    nudges = _get("/nudges/pending")
    assert len(nudges) > 0, "Expected at least one nudge"
    nid = nudges[0]["id"]

    result = _post("/nudges/dismiss", {"id": nid})
    assert result.get("ok") is True, f"Expected ok=True: {result}"

    remaining = _get("/nudges/pending")
    assert nid not in [n["id"] for n in remaining], f"Nudge {nid} still present"
    print(f"  PASS POST /nudges/dismiss (id={nid})")


def test_nudge_dismiss_all():
    """POST /nudges/dismiss-all must clear all nudges."""
    fire_at = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    _post("/reminders/add", {"text": "Clear 1", "fire_at": fire_at})
    _post("/reminders/add", {"text": "Clear 2", "fire_at": fire_at})
    _get("/nudges/pending")  # trigger firing

    result = _post("/nudges/dismiss-all", {})
    assert result.get("ok") is True, f"Expected ok=True: {result}"

    remaining = _get("/nudges/pending")
    assert len(remaining) == 0, f"Expected 0 nudges, got {len(remaining)}"
    print(f"  PASS POST /nudges/dismiss-all: cleared {result.get('dismissed', '?')} nudges")


# ── Reminder store unit tests ─────────────────────────────────────────────

def test_execute_reminder_set_valid():
    """execute_reminder_set with valid ISO time must succeed."""
    import asyncio
    from backend.reminder_store import execute_reminder_set, delete_reminder, list_reminders
    fire_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    result  = asyncio.run(execute_reminder_set({"text": "Unit test reminder", "when": fire_at}))
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert "unit test" in result.lower() or "reminder" in result.lower() or "done" in result.lower(), \
        f"Unexpected result: {result!r}"
    # Clean up
    reminders = list_reminders()
    for r in reminders:
        if "unit test" in r.get("text", "").lower():
            delete_reminder(r["id"])
    print(f"  PASS execute_reminder_set valid: {result[:80]!r}")


def test_execute_reminder_set_bad_time():
    """execute_reminder_set with invalid time must return error string."""
    import asyncio
    from backend.reminder_store import execute_reminder_set
    result = asyncio.run(execute_reminder_set({"text": "Bad time", "when": "not-a-date"}))
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert "parse" in result.lower() or "couldn't" in result.lower() or "invalid" in result.lower() or "failed" in result.lower(), \
        f"Expected error message, got: {result!r}"
    print(f"  PASS execute_reminder_set bad time: returns error")


# ── Tool list tests ───────────────────────────────────────────────────────

def test_set_reminder_always_in_tools():
    """set_reminder must always be in _build_tools() regardless of integrations."""
    from backend.claude_client import _build_tools
    tools      = _build_tools()
    tool_names = [t["name"] for t in tools]
    assert "set_reminder" in tool_names, f"set_reminder missing from tools: {tool_names}"
    print(f"  PASS _build_tools() always includes set_reminder: {tool_names}")


# ── Calendar tests ────────────────────────────────────────────────────────

def test_calendar_status_endpoint():
    """GET /calendar/status must return {connected}."""
    data = _get("/calendar/status")
    assert "connected" in data, f"Missing 'connected': {data}"
    assert isinstance(data["connected"], bool), f"connected must be bool: {data}"
    print(f"  PASS GET /calendar/status: connected={data['connected']}")


def test_calendar_auth_url_without_credentials():
    """GET /calendar/auth-url without Google credentials must return 400."""
    from backend.secure_store import get_secret, delete_secret, set_secret
    orig_id     = get_secret("google_client_id")
    orig_secret = get_secret("google_client_secret")
    try:
        delete_secret("google_client_id")
        delete_secret("google_client_secret")
        try:
            _get("/calendar/auth-url")
            assert False, "Expected 400 but got success"
        except urllib.error.HTTPError as e:
            assert e.code == 400, f"Expected 400, got {e.code}"
            print("  PASS GET /calendar/auth-url without credentials returns 400")
    finally:
        if orig_id:     set_secret("google_client_id",     orig_id)
        if orig_secret: set_secret("google_client_secret", orig_secret)


def test_format_events_for_claude_empty():
    """format_events_for_claude([]) must return a no-events message."""
    from backend.integrations.calendar import format_events_for_claude
    result = format_events_for_claude([])
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert "no" in result.lower() or "not" in result.lower(), \
        f"Expected no-events message: {result!r}"
    print("  PASS format_events_for_claude([]) returns no-events string")


def test_format_events_for_claude_with_data():
    """format_events_for_claude with sample data must include title and time."""
    from backend.integrations.calendar import format_events_for_claude
    sample = [
        {"id": "abc", "summary": "Team Stand-up", "start": "2026-05-10T09:00:00+05:30",
         "end": "2026-05-10T09:30:00+05:30", "location": "Google Meet"},
    ]
    result = format_events_for_claude(sample)
    assert "Team Stand-up" in result, f"Missing event title: {result!r}"
    print("  PASS format_events_for_claude with data includes title")


def test_execute_calendar_check_disconnected():
    """execute_calendar_check when not connected must return guidance."""
    import asyncio
    from backend.integrations.calendar import execute_calendar_check, get_status
    if get_status()["connected"]:
        print("  SKIP execute_calendar_check disconnected (Calendar is actually connected)")
        return
    result = asyncio.run(execute_calendar_check({}))
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert "settings" in result.lower() or "calendar" in result.lower(), \
        f"Should mention settings or calendar: {result!r}"
    print(f"  PASS execute_calendar_check disconnected: returns guidance ({len(result)} chars)")


# ── Health check ──────────────────────────────────────────────────────────

def test_health_version():
    """GET /health must report phase7 version."""
    data = _get("/health")
    assert data.get("version") == "1.0.0-phase7", \
        f"Expected phase7 version, got: {data.get('version')!r}"
    print(f"  PASS GET /health: version={data['version']}")


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        test_health_version,
        test_reminder_add_and_list,
        test_reminder_delete,
        test_nudge_fired_for_past_reminder,
        test_nudge_dismiss,
        test_nudge_dismiss_all,
        test_execute_reminder_set_valid,
        test_execute_reminder_set_bad_time,
        test_set_reminder_always_in_tools,
        test_calendar_status_endpoint,
        test_calendar_auth_url_without_credentials,
        test_format_events_for_claude_empty,
        test_format_events_for_claude_with_data,
        test_execute_calendar_check_disconnected,
    ]
    failures = []

    print("\n=== AuraBot Phase 7 Self-Test ===\n")
    print("Waiting for backend...")
    for _ in range(30):
        try:
            _get("/health")
            break
        except Exception:
            time.sleep(1)
    else:
        print("FAIL: Backend not reachable. Start the app (npm start) then re-run.")
        sys.exit(1)

    print("Backend is up. Running tests...\n")
    print("NOTE: Full Calendar tests require a connected Google account.")
    print("      Connect Calendar in Settings -> API Keys to test the complete flow.\n")

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
        print(f"RESULT: All {len(tests)} tests passed. Phase 7 is complete!")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
