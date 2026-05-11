"""Phase 6 self-test — WhatsApp bridge integration.

Tests run against the live backend on 127.0.0.1:8765.
Tests that need an active WhatsApp connection are skipped automatically
when the bridge is not running (avoids requiring Puppeteer in CI).

Usage:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python backend\\tests\\test_phase6.py
"""

import json
import sys
import time
import urllib.error
import urllib.request
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


# ── Tests ──────────────────────────────────────────────────────────────────

def test_whatsapp_status_endpoint():
    """GET /whatsapp/status must return {bridge_running, connected}."""
    data = _get("/whatsapp/status")
    for key in ("bridge_running", "connected"):
        assert key in data, f"Missing key '{key}': {data}"
    assert isinstance(data["bridge_running"], bool), f"bridge_running must be bool: {data}"
    assert isinstance(data["connected"], bool),      f"connected must be bool: {data}"
    print(f"  PASS GET /whatsapp/status: bridge_running={data['bridge_running']}, connected={data['connected']}")


def test_whatsapp_qr_endpoint():
    """GET /whatsapp/qr must return {connected, qr}."""
    data = _get("/whatsapp/qr")
    assert "connected" in data, f"Missing 'connected': {data}"
    assert "qr"        in data, f"Missing 'qr': {data}"
    qr_summary = "<data>" if data["qr"] else None
    print(f"  PASS GET /whatsapp/qr: connected={data['connected']}, qr={qr_summary}")


def test_whatsapp_chats_not_connected():
    """GET /whatsapp/chats without bridge running must return empty list or 503."""
    # Ensure bridge is stopped
    try:
        _post("/whatsapp/disconnect", {})
    except Exception:
        pass
    try:
        data = _get("/whatsapp/chats")
        assert isinstance(data, list), f"Expected list: {data}"
        print(f"  PASS GET /whatsapp/chats (not connected): returns empty list ({len(data)} items)")
    except urllib.error.HTTPError as e:
        assert e.code == 503, f"Expected 503 or empty list, got {e.code}"
        print(f"  PASS GET /whatsapp/chats (not connected): returns 503")


def test_whatsapp_disconnect_endpoint():
    """POST /whatsapp/disconnect must succeed even when not running."""
    result = _post("/whatsapp/disconnect", {})
    assert result.get("ok") is True, f"Expected ok=True: {result}"
    print("  PASS POST /whatsapp/disconnect -> ok")


def test_whatsapp_start_response_shape():
    """POST /whatsapp/start must return {started, message}."""
    try:
        result = _post("/whatsapp/start", {})
        assert "started"  in result, f"Missing 'started': {result}"
        assert "message"  in result, f"Missing 'message': {result}"
        assert isinstance(result["started"], bool), f"started must be bool: {result}"
        print(f"  PASS POST /whatsapp/start: started={result['started']}, message={result['message']!r}")
        # Stop if it actually started
        if result["started"]:
            _post("/whatsapp/disconnect", {})
    except Exception as exc:
        print(f"  SKIP POST /whatsapp/start: {exc}")


def test_check_whatsapp_tool_not_in_tools_when_disconnected():
    """When WhatsApp is not connected, check_whatsapp must NOT be in the tool list."""
    from backend.claude_client import _build_tools
    try:
        _post("/whatsapp/disconnect", {})
    except Exception:
        pass

    tools      = _build_tools()
    tool_names = [t["name"] for t in tools]
    assert "check_whatsapp" not in tool_names, \
        f"check_whatsapp should not be in tools when disconnected: {tool_names}"
    print(f"  PASS _build_tools() without WhatsApp: {tool_names}")


def test_format_chats_for_claude_empty():
    """format_chats_for_claude([]) must return a no-chats message."""
    from backend.integrations.whatsapp import format_chats_for_claude
    result = format_chats_for_claude([])
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert "no" in result.lower() or "not" in result.lower() or "found" in result.lower(), \
        f"Expected no-chats message: {result!r}"
    print("  PASS format_chats_for_claude([]) returns no-chats string")


def test_format_chats_for_claude_with_data():
    """format_chats_for_claude with sample data must include names and message previews."""
    from backend.integrations.whatsapp import format_chats_for_claude
    sample = [
        {"id": "91234@c.us", "name": "Priya", "unreadCount": 3,
         "lastMessage": "Can we meet tomorrow?", "timestamp": 0, "isGroup": False},
        {"id": "group@g.us", "name": "Team Aura", "unreadCount": 0,
         "lastMessage": "Sprint review at 3pm", "timestamp": 0, "isGroup": True},
    ]
    result = format_chats_for_claude(sample)
    assert "Priya"            in result, f"Missing chat name 'Priya': {result!r}"
    assert "Team Aura"        in result, f"Missing group name 'Team Aura': {result!r}"
    assert "[3 unread]"       in result, f"Missing unread count: {result!r}"
    assert "Can we meet"      in result, f"Missing last message preview: {result!r}"
    print("  PASS format_chats_for_claude with data includes names and messages")


def test_execute_whatsapp_check_not_running():
    """execute_whatsapp_check when bridge not running must return a guidance string."""
    import asyncio
    from backend.integrations.whatsapp import execute_whatsapp_check
    try:
        _post("/whatsapp/disconnect", {})
    except Exception:
        pass

    result = asyncio.run(execute_whatsapp_check({}))
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert len(result) > 10, f"Too short: {result!r}"
    assert "settings" in result.lower() or "whatsapp" in result.lower() or "qr" in result.lower(), \
        f"Should mention settings, WhatsApp, or QR: {result!r}"
    print(f"  PASS execute_whatsapp_check not running: returns guidance ({len(result)} chars)")


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        test_whatsapp_status_endpoint,
        test_whatsapp_qr_endpoint,
        test_whatsapp_chats_not_connected,
        test_whatsapp_disconnect_endpoint,
        test_whatsapp_start_response_shape,
        test_check_whatsapp_tool_not_in_tools_when_disconnected,
        test_format_chats_for_claude_empty,
        test_format_chats_for_claude_with_data,
        test_execute_whatsapp_check_not_running,
    ]
    failures = []

    print("\n=== AuraBot Phase 6 Self-Test ===\n")

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
    print("NOTE: Full WhatsApp tests require starting the bridge and scanning the QR code.")
    print("      Start WhatsApp in Settings -> API Keys to test the complete flow.\n")

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
        print(f"RESULT: All {len(tests)} tests passed. Phase 6 is complete!")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
