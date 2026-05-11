"""Phase 5 self-test — Gmail OAuth integration.

Tests run against the live backend on 127.0.0.1:8765.
Full Gmail tests (email reading) require a connected account.

Usage:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python backend\\tests\\test_phase5.py
"""

import json
import sys
import time
import urllib.request
import urllib.parse
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


def _post_raw_bytes(path, body=None):
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


# ── Tests ──────────────────────────────────────────────────────────────────

def test_gmail_status_endpoint():
    """GET /gmail/status must return {connected, email}."""
    data = _get("/gmail/status")
    assert "connected" in data, f"Missing 'connected': {data}"
    assert "email" in data,     f"Missing 'email': {data}"
    assert isinstance(data["connected"], bool), f"connected must be bool: {data}"
    print(f"  PASS GET /gmail/status: connected={data['connected']}, email={data['email']!r}")


def test_gmail_auth_url_no_credentials():
    """GET /gmail/auth-url with no Google credentials must return 400."""
    from backend.secure_store import get_secret, delete_secret, set_secret

    orig_id     = get_secret("google_client_id")
    orig_secret = get_secret("google_client_secret")

    try:
        delete_secret("google_client_id")
        delete_secret("google_client_secret")

        try:
            _get("/gmail/auth-url")
            assert False, "Expected 400 but got success"
        except urllib.error.HTTPError as e:
            assert e.code == 400, f"Expected 400, got {e.code}"
            print("  PASS GET /gmail/auth-url without credentials returns 400")
    finally:
        if orig_id:     set_secret("google_client_id",     orig_id)
        if orig_secret: set_secret("google_client_secret", orig_secret)


def test_gmail_auth_url_with_credentials():
    """GET /gmail/auth-url with credentials set must return a Google OAuth URL."""
    from backend.secure_store import get_secret, set_secret

    if not get_secret("google_client_id") or not get_secret("google_client_secret"):
        print("  SKIP GET /gmail/auth-url (no Google credentials set — add them in Settings to test)")
        return

    data = _get("/gmail/auth-url")
    assert "url" in data, f"Missing 'url': {data}"
    assert "accounts.google.com" in data["url"], \
        f"URL does not point to Google: {data['url'][:80]!r}"
    print(f"  PASS GET /gmail/auth-url returns Google OAuth URL")


def test_gmail_disconnect_endpoint():
    """POST /gmail/disconnect must succeed and status must show disconnected."""
    result = _post("/gmail/disconnect")
    assert result.get("ok") is True, f"Expected ok=True: {result}"

    status = _get("/gmail/status")
    assert status["connected"] is False, f"Expected disconnected after disconnect: {status}"
    print("  PASS POST /gmail/disconnect -> status shows disconnected")


def test_gmail_unread_disconnected():
    """GET /gmail/unread without a connected account must return empty list."""
    # Ensure disconnected first
    _post("/gmail/disconnect")
    data = _get("/gmail/unread")
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    assert len(data) == 0, f"Expected empty list when disconnected, got {len(data)} items"
    print("  PASS GET /gmail/unread when disconnected returns []")


def test_check_email_tool_not_in_tools_when_disconnected():
    """When Gmail is disconnected, check_email tool must NOT be offered to Claude."""
    from backend.claude_client import _build_tools
    _post("/gmail/disconnect")

    tools      = _build_tools()
    tool_names = [t["name"] for t in tools]
    assert "check_email" not in tool_names, \
        f"check_email should not be in tools when disconnected: {tool_names}"
    print(f"  PASS _build_tools() without Gmail: {tool_names}")


def test_format_emails_for_claude_empty():
    """format_emails_for_claude([]) must return a no-emails message."""
    from backend.integrations.gmail import format_emails_for_claude
    result = format_emails_for_claude([])
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert "no unread" in result.lower(), f"Expected no-emails message: {result!r}"
    print("  PASS format_emails_for_claude([]) returns no-emails string")


def test_format_emails_for_claude_with_data():
    """format_emails_for_claude with sample data must include all fields."""
    from backend.integrations.gmail import format_emails_for_claude
    sample = [
        {"id": "abc", "subject": "Q1 Review", "sender": "boss@example.com",
         "snippet": "Please review the attached report.", "date": "Mon, 5 May 2025 10:00 IST"},
    ]
    result = format_emails_for_claude(sample)
    assert "Q1 Review"            in result, f"Subject missing: {result!r}"
    assert "boss@example.com"     in result, f"Sender missing: {result!r}"
    assert "Please review"        in result, f"Snippet missing: {result!r}"
    print("  PASS format_emails_for_claude with data includes all fields")


def test_execute_email_check_disconnected():
    """execute_email_check when disconnected must return a guidance string."""
    import asyncio
    from backend.integrations.gmail import execute_email_check
    _post("/gmail/disconnect")

    result = asyncio.run(execute_email_check({}))
    assert isinstance(result, str), f"Expected str: {type(result)}"
    assert len(result) > 10, f"Too short: {result!r}"
    # Should contain guidance about connecting
    assert "connect" in result.lower() or "settings" in result.lower(), \
        f"Should mention connecting Gmail: {result!r}"
    print(f"  PASS execute_email_check disconnected: returns guidance ({len(result)} chars)")


def test_callback_missing_code():
    """GET /gmail/callback without code must return 400."""
    try:
        _get("/gmail/callback")
        assert False, "Expected 400 but got success"
    except urllib.error.HTTPError as e:
        assert e.code == 400, f"Expected 400, got {e.code}"
        print("  PASS GET /gmail/callback without code returns 400")


def test_gmail_status_in_secrets_status():
    """GET /secrets/status should include google keys."""
    data = _get("/secrets/status")
    assert "google_client_id" in data,     f"google_client_id missing from secrets/status: {data}"
    assert "google_client_secret" in data, f"google_client_secret missing: {data}"
    print(f"  PASS GET /secrets/status includes Google keys: {data}")


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        test_gmail_status_endpoint,
        test_gmail_auth_url_no_credentials,
        test_gmail_auth_url_with_credentials,
        test_gmail_disconnect_endpoint,
        test_gmail_unread_disconnected,
        test_check_email_tool_not_in_tools_when_disconnected,
        test_format_emails_for_claude_empty,
        test_format_emails_for_claude_with_data,
        test_execute_email_check_disconnected,
        test_callback_missing_code,
        test_gmail_status_in_secrets_status,
    ]
    failures = []

    print("\n=== AuraBot Phase 5 Self-Test ===\n")

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
    print("NOTE: Full Gmail tests (email reading) require a connected Google account.")
    print("      Connect Gmail in Settings -> API Keys to test the complete flow.\n")

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
        print(f"RESULT: All {len(tests)} tests passed. Phase 5 is complete!")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
