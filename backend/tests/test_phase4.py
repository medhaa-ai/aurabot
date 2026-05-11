"""Phase 4 self-test — ChromaDB conversation memory.

Tests run against the live backend on 127.0.0.1:8765
AND directly against the memory_store module.

Usage:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python backend\\tests\\test_phase4.py
"""

import json
import sys
import time
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


def _post(path, body):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


# ── Unit tests (direct module) ─────────────────────────────────────────────

def test_embed_deterministic():
    """_embed must return same vector for same input."""
    from backend.memory_store import _embed

    v1 = _embed("hello world how are you")
    v2 = _embed("hello world how are you")
    v3 = _embed("completely different text about cats")

    assert v1 == v2, "Embedding is not deterministic"
    assert v1 != v3, "Different texts must produce different embeddings"
    assert len(v1) == 384, f"Expected 384-dim vector, got {len(v1)}"
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-6, "Vector not normalized"
    print("  PASS _embed: deterministic, 384-dim, L2-normalized")


def test_add_and_stats():
    """add_turn must increment count; get_stats must reflect the change."""
    from backend.memory_store import add_turn, get_stats, wipe_all

    # Start clean
    wipe_all()
    stats0 = get_stats()
    assert stats0["count"] == 0, f"Expected 0 after wipe, got {stats0['count']}"

    turn_id = add_turn("What is the capital of India?", "New Delhi is the capital of India.")
    assert isinstance(turn_id, str) and turn_id.startswith("turn_"), \
        f"Unexpected turn_id: {turn_id!r}"

    stats1 = get_stats()
    assert stats1["count"] == 1, f"Expected count=1, got {stats1['count']}"
    assert stats1["last_date"] is not None, "last_date must be set after adding a turn"
    print(f"  PASS add_turn + get_stats: count=1, date={stats1['last_date']!r}")


def test_query_similar():
    """query_similar must return related turns; unrelated queries score lower."""
    from backend.memory_store import add_turn, query_similar, wipe_all

    wipe_all()
    add_turn("What coffee does the office use?",    "The office uses Blue Tokai beans.")
    add_turn("Remind me about the board meeting.",  "Board meeting is on Friday at 3 PM.")
    add_turn("What is my laptop model?",            "Your laptop is a Dell XPS 15.")

    results = query_similar("coffee beans office", n_results=3)
    assert results, "No results returned"
    assert results[0]["metadata"]["user"].startswith("What coffee"), \
        f"Top result should be the coffee turn, got: {results[0]['metadata']['user']!r}"
    print(f"  PASS query_similar: top result is the coffee turn (distance={results[0]['distance']})")


def test_delete_by_ids():
    """delete_by_ids must remove specific entries."""
    from backend.memory_store import add_turn, delete_by_ids, get_stats

    id1 = add_turn("Delete test message 1", "Response 1")
    id2 = add_turn("Delete test message 2", "Response 2")

    count_before = get_stats()["count"]
    deleted = delete_by_ids([id1, id2])
    count_after = get_stats()["count"]

    assert deleted == 2, f"Expected 2 deleted, got {deleted}"
    assert count_after == count_before - 2, \
        f"Count should decrease by 2: {count_before} -> {count_after}"
    print(f"  PASS delete_by_ids: {deleted} entries removed")


def test_export_all():
    """export_all must return list of dicts with id and metadata."""
    from backend.memory_store import add_turn, export_all, wipe_all

    wipe_all()
    add_turn("Export test user message", "Export test bot response")
    exported = export_all()

    assert isinstance(exported, list), f"Expected list, got {type(exported)}"
    assert len(exported) == 1, f"Expected 1 exported entry, got {len(exported)}"
    entry = exported[0]
    assert "id" in entry,       "Exported entry must have 'id'"
    assert "metadata" in entry, "Exported entry must have 'metadata'"
    assert "user" in entry["metadata"], "Metadata must have 'user'"
    assert "bot" in entry["metadata"],  "Metadata must have 'bot'"
    print(f"  PASS export_all: 1 entry exported with correct structure")


def test_wipe_all():
    """wipe_all must delete everything and return correct count."""
    from backend.memory_store import add_turn, wipe_all, get_stats

    add_turn("Wipe test 1", "Bot response 1")
    add_turn("Wipe test 2", "Bot response 2")
    count_before = get_stats()["count"]

    deleted = wipe_all()
    stats   = get_stats()

    assert deleted >= 2, f"Expected >=2 deleted, got {deleted}"
    assert stats["count"] == 0, f"Count after wipe must be 0, got {stats['count']}"
    print(f"  PASS wipe_all: deleted {deleted} entries, count now 0")


# ── Integration tests (via HTTP) ───────────────────────────────────────────

def test_memory_stats_endpoint():
    """GET /memory/stats must return count and last_date."""
    data = _get("/memory/stats")
    assert "count" in data, f"No 'count' in stats: {data}"
    assert "last_date" in data, f"No 'last_date' in stats: {data}"
    assert isinstance(data["count"], int), f"count must be int: {data}"
    print(f"  PASS GET /memory/stats: count={data['count']}, last_date={data['last_date']!r}")


def test_memory_search_endpoint():
    """GET /memory/search?q=... must return a list."""
    _post("/memory/add", {"user": "Endpoint search test phrase", "bot": "Bot endpoint search reply"})

    data = _get("/memory/search?q=endpoint+search+test")
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    print(f"  PASS GET /memory/search: {len(data)} result(s)")


def test_memory_wipe_endpoint():
    """POST /memory/wipe must delete all and return ok."""
    result = _post("/memory/wipe", {})
    assert result.get("ok") is True, f"Expected ok=True: {result}"
    assert "deleted" in result, f"No 'deleted' in wipe response: {result}"

    stats = _get("/memory/stats")
    assert stats["count"] == 0, f"After wipe, count must be 0: {stats}"
    print(f"  PASS POST /memory/wipe: deleted={result['deleted']}, count now 0")


def test_memory_export_endpoint():
    """GET /memory/export must return a JSON array."""
    data = _get("/memory/export")
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    print(f"  PASS GET /memory/export: {len(data)} entries")


def test_memory_delete_endpoint():
    """POST /memory/delete with ids must remove those entries."""
    r1 = _post("/memory/add", {"user": "Delete endpoint test 1", "bot": "Bot reply 1"})
    r2 = _post("/memory/add", {"user": "Delete endpoint test 2", "bot": "Bot reply 2"})
    id1, id2 = r1["id"], r2["id"]

    result = _post("/memory/delete", {"ids": [id1, id2]})
    assert result.get("ok") is True,  f"Expected ok=True: {result}"
    assert result.get("deleted") == 2, f"Expected deleted=2: {result}"
    print(f"  PASS POST /memory/delete: 2 specific entries deleted")


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        # Unit tests (no backend needed)
        test_embed_deterministic,
        test_add_and_stats,
        test_query_similar,
        test_delete_by_ids,
        test_export_all,
        test_wipe_all,
        # Integration tests (backend needed)
        test_memory_stats_endpoint,
        test_memory_search_endpoint,
        test_memory_wipe_endpoint,
        test_memory_export_endpoint,
        test_memory_delete_endpoint,
    ]
    failures = []

    print("\n=== AuraBot Phase 4 Self-Test ===\n")

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

    for t in tests:
        try:
            t()
        except AssertionError as err:
            print(f"  FAIL {t.__name__}: {err}")
            failures.append(t.__name__)
        except Exception as err:
            print(f"  ERROR {t.__name__}: {err}")
            failures.append(t.__name__)

    # Final cleanup
    try:
        from backend.memory_store import wipe_all
        wipe_all()
    except Exception:
        pass

    print()
    if failures:
        print(f"RESULT: {len(failures)}/{len(tests)} tests FAILED: {', '.join(failures)}")
        sys.exit(1)
    else:
        print(f"RESULT: All {len(tests)} tests passed. Phase 4 is complete!")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
