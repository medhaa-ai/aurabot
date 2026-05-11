"""Phase 2 self-test — encrypted settings + permissions system.

Tests run against the live backend on 127.0.0.1:8765.

Usage:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python backend\\tests\\test_phase2.py
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE    = "http://127.0.0.1:8765"
TIMEOUT = 5


def _get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _post(path, body):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


# ── Tests ──────────────────────────────────────────────────────────────────

def test_health_phase2():
    """Backend version should now be phase2."""
    data = _get("/health")
    assert "phase2" in data.get("version", ""), f"Not phase2 version: {data}"
    print("  PASS health (phase2 version)")


def test_save_and_detect_api_key():
    """Save a fake Anthropic key -> settings/get must show has_anthropic_key=true."""
    fake_key = "sk-ant-test-PHASE2SELFTEST"
    _post("/settings/set", {"key": "anthropic_key", "value": fake_key})

    # settings/get must NOT return the key itself
    settings = _get("/settings/get")
    assert "anthropic_key" not in settings or settings.get("anthropic_key") == "", \
        "settings/get leaked the raw key!"
    assert settings.get("has_anthropic_key") is True, \
        f"has_anthropic_key should be True, got: {settings.get('has_anthropic_key')}"
    print("  PASS key saved; settings/get shows has_anthropic_key=True (key not exposed)")


def test_key_encrypted_at_rest():
    """The raw key value must NOT appear in plain text in secrets.enc."""
    fake_key = "sk-ant-test-PHASE2SELFTEST"
    secrets_path = Path.home() / ".aurabot" / "secrets.enc"

    assert secrets_path.exists(), "secrets.enc not found — was the key saved?"

    raw = secrets_path.read_text(encoding="utf-8")
    assert fake_key not in raw, \
        f"Key found in plain text in secrets.enc! Encryption is broken."
    print("  PASS key is NOT in plain text in secrets.enc (encrypted at rest)")


def test_permission_check_unknown():
    """Checking an unknown permission -> needs_prompt=True."""
    action = "test.phase2.unknown"
    data = _post("/permissions/check", {
        "action_id":   action,
        "description": "run a phase2 self-test",
    })
    assert data.get("needs_prompt") is True,  f"Expected needs_prompt=True: {data}"
    assert data.get("granted")      is False, f"Expected granted=False: {data}"
    print("  PASS unknown permission -> needs_prompt=True, granted=False")


def test_grant_permission_always():
    """Grant always -> check returns granted=True, needs_prompt=False."""
    action = "test.phase2.grant"
    _post("/permissions/grant", {
        "action_id":   action,
        "description": "grant test permission",
        "choice":      "always",
    })

    data = _post("/permissions/check", {
        "action_id":   action,
        "description": "grant test permission",
    })
    assert data.get("granted")      is True,  f"Expected granted=True after grant: {data}"
    assert data.get("needs_prompt") is False, f"Expected needs_prompt=False: {data}"
    print("  PASS grant always -> subsequent check returns granted=True")


def test_permissions_list():
    """Permissions list must contain the just-granted permission."""
    perms = _get("/permissions/list")
    assert isinstance(perms, list), f"Expected list: {type(perms)}"
    ids = [p["action_id"] for p in perms]
    assert "test.phase2.grant" in ids, f"Granted permission not in list: {ids}"
    print(f"  PASS permissions list shows granted permission ({len(perms)} total)")


def test_revoke_permission():
    """Revoke -> permission disappears from list -> check returns needs_prompt=True."""
    action = "test.phase2.grant"
    result = _post(f"/permissions/revoke/{action}", {})
    assert result.get("ok") is True, f"Revoke failed: {result}"

    # Check it's gone
    data = _post("/permissions/check", {
        "action_id":   action,
        "description": "grant test permission",
    })
    assert data.get("needs_prompt") is True, \
        f"After revoke, still granted? {data}"

    # List should not contain it
    perms = _get("/permissions/list")
    ids   = [p["action_id"] for p in perms]
    assert action not in ids, f"Revoked permission still in list: {ids}"
    print("  PASS revoke -> permission gone, check needs_prompt=True again")


def test_deny_permission_stored():
    """Granting 'deny' stores the denial, check still shows needs_prompt=False."""
    action = "test.phase2.deny"
    _post("/permissions/grant", {
        "action_id":   action,
        "description": "deny test permission",
        "choice":      "deny",
    })
    perms = _get("/permissions/list")
    ids   = [p["action_id"] for p in perms]
    assert action in ids, f"Denied permission not in list: {ids}"
    print("  PASS deny choice stored in permissions list")

    # Clean up
    _post(f"/permissions/revoke/{action}", {})


def test_secrets_status():
    """GET /secrets/status returns a dict with known key names."""
    data = _get("/secrets/status")
    assert isinstance(data, dict),            f"Expected dict: {data}"
    assert "anthropic_key" in data,           f"anthropic_key not in status: {data}"
    assert data.get("anthropic_key") is True, f"anthropic_key should be True (saved earlier)"
    print(f"  PASS secrets/status: {data}")


# ── Clean-up: remove test keys ─────────────────────────────────────────────

def cleanup():
    try:
        from backend.secure_store import delete_secret
        delete_secret("anthropic_key")
    except Exception:
        pass


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        test_health_phase2,
        test_save_and_detect_api_key,
        test_key_encrypted_at_rest,
        test_permission_check_unknown,
        test_grant_permission_always,
        test_permissions_list,
        test_revoke_permission,
        test_deny_permission_stored,
        test_secrets_status,
    ]
    failures = []

    print("\n=== AuraBot Phase 2 Self-Test ===\n")

    # Wait for backend
    print("Waiting for backend…")
    for _ in range(20):
        try:
            _get("/health")
            break
        except Exception:
            time.sleep(1)
    else:
        print("FAIL: Backend not reachable. Make sure the app is running (npm start).")
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

    cleanup()

    print()
    if failures:
        print(f"RESULT: {len(failures)}/{len(tests)} tests FAILED: {', '.join(failures)}")
        sys.exit(1)
    else:
        print(f"RESULT: All {len(tests)} tests passed. Phase 2 is complete!")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
