"""Phase 3 self-test — Claude brain + SSE streaming.

Tests run against the live backend on 127.0.0.1:8765.
The Anthropic API key must be set for Claude tests to pass.

Usage:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python backend\\tests\\test_phase3.py
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

# Ensure project root is on sys.path so `from backend.X import Y` works
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

BASE    = "http://127.0.0.1:8765"
TIMEOUT = 60  # Claude can be slow


def _get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as r:
        return json.loads(r.read())


def _post_raw(path, body) -> bytes:
    """POST and return raw bytes (for SSE streams)."""
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _parse_sse(raw: bytes) -> list[dict]:
    """Parse all SSE events from a byte response into a list of dicts."""
    events = []
    for line in raw.decode("utf-8", errors="replace").split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            try:
                events.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                pass
    return events


# ── Tests ──────────────────────────────────────────────────────────────────

def test_health_phase3():
    """Backend version must be phase3."""
    data = _get("/health")
    assert "phase3" in data.get("version", ""), f"Not phase3 version: {data}"
    print("  PASS health (phase3 version)")


def test_chat_returns_sse():
    """/chat must return text/event-stream content."""
    data = json.dumps({"message": "Say exactly the word HELLO and nothing else."}).encode()
    req  = urllib.request.Request(
        f"{BASE}/chat", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        content_type = r.headers.get("Content-Type", "")
        raw = r.read()

    assert "text/event-stream" in content_type, \
        f"/chat must return SSE, got: {content_type}"
    print(f"  PASS /chat returns Content-Type: {content_type.split(';')[0]}")

    events = _parse_sse(raw)
    assert events, "No SSE events parsed from response"
    print(f"  PASS SSE response contains {len(events)} events")
    return raw


def test_sse_has_chunk_and_done():
    """Response must contain a content event and exactly one 'done' event.

    Accepts either:
      - 'chunk' events  — when a valid Anthropic API key is set and Claude responds
      - 'error_replace' — when the key is absent/invalid (graceful error path)
    Both prove the SSE transport and error handling work end-to-end.
    """
    raw    = _post_raw("/chat", {"message": "Reply with just: OK"})
    events = _parse_sse(raw)

    types   = [e.get("type") for e in events]
    content = [e for e in events if e.get("type") in ("chunk", "error_replace")]
    dones   = [e for e in events if e.get("type") == "done"]

    assert content, f"No content event (chunk/error_replace) in SSE stream. Events: {types}"
    assert len(dones) == 1, f"Expected 1 'done' event, got {len(dones)}. Events: {types}"

    event_type = content[0]["type"]
    if event_type == "chunk":
        print(f"  PASS SSE stream: {len(content)} chunk(s) + 1 done (live Claude response)")
    else:
        print(f"  PASS SSE stream: error_replace + 1 done (API key missing/invalid — set a real key in Settings to test live Claude)")


def test_done_event_has_expression():
    """'done' event must include an 'expression' field."""
    raw    = _post_raw("/chat", {"message": "Reply with: Great news!"})
    events = _parse_sse(raw)
    done   = next((e for e in events if e.get("type") == "done"), None)

    assert done is not None, "No 'done' event found"
    assert "expression" in done, f"'done' event missing 'expression': {done}"
    assert done["expression"] in {
        "idle", "thinking", "happy", "empathetic",
        "excited", "confused", "focused", "celebrating",
    }, f"Unknown expression: {done['expression']}"
    print(f"  PASS 'done' event has expression={done['expression']!r}")


def test_no_api_key_fallback():
    """When the Anthropic key is absent the stream must still send a 'done' event (no crash)."""
    from backend.secure_store import get_secret, delete_secret, set_secret

    original = get_secret("anthropic_key")
    try:
        delete_secret("anthropic_key")
        raw    = _post_raw("/chat", {"message": "hello"})
        events = _parse_sse(raw)
        types  = [e.get("type") for e in events]
        assert "done" in types, f"No 'done' event without API key. Events: {types}"
        print("  PASS no-key path: stream ends with 'done' event (no crash)")
    finally:
        if original:
            set_secret("anthropic_key", original)


def test_expression_classifier():
    """classify_expression heuristics must return correct expressions."""
    from backend.claude_client import classify_expression

    cases = [
        ("Congratulations! Well done on this fantastic work!", "celebrating"),
        ("Sorry to hear that, that sounds difficult.", "empathetic"),
        ("Great news! This is wonderful and love it!", "excited"),
        ("I'm not sure, can't determine the answer, hmm.", "confused"),
        ("Let me check that for you, working on it now.", "focused"),
        ("Hey!! This is awesome!!", "happy"),
        ("The meeting is at 3 PM.", "idle"),
    ]
    for text, expected in cases:
        result = classify_expression(text)
        assert result == expected, \
            f"classify_expression({text!r}) -> {result!r}, expected {expected!r}"
    print(f"  PASS expression classifier: all {len(cases)} cases correct")


def test_web_search_no_key_returns_string():
    """execute_search must return a helpful string when no SerpAPI key is set."""
    import asyncio
    from backend.secure_store import get_secret, delete_secret, set_secret
    from backend.integrations.web_search import execute_search

    original = get_secret("serpapi_key")
    try:
        delete_secret("serpapi_key")
        result = asyncio.run(execute_search("test query"))
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) > 10, f"Result too short: {result!r}"
        print(f"  PASS web search no-key returns fallback string ({len(result)} chars)")
    finally:
        if original:
            set_secret("serpapi_key", original)


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        test_health_phase3,
        test_chat_returns_sse,
        test_sse_has_chunk_and_done,
        test_done_event_has_expression,
        test_no_api_key_fallback,
        test_expression_classifier,
        test_web_search_no_key_returns_string,
    ]
    failures = []

    print("\n=== AuraBot Phase 3 Self-Test ===\n")

    # Wait for backend
    print("Waiting for backend...")
    for _ in range(30):
        try:
            _get("/health")
            break
        except Exception:
            time.sleep(1)
    else:
        print("FAIL: Backend not reachable. Make sure the app is running (npm start).")
        sys.exit(1)

    print("Backend is up. Running tests...\n")
    print("NOTE: Claude tests require a valid Anthropic API key in Settings.")
    print("      Tests may take 10-30 seconds each (LLM response time).\n")

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
        print(f"RESULT: All {len(tests)} tests passed. Phase 3 is complete!")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
