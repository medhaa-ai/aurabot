"""ChromaDB-backed episodic (long-term) conversation memory.

Persist path: ~/.aurabot/chromadb/
Collection:   aurabot_memory

Public API:
    add_turn(user_msg, bot_msg) -> turn_id
    query_similar(text, n_results) -> [{"id", "document", "metadata", "distance"}]
    search_memory(query, n_results) -> same
    get_stats() -> {"count", "last_date"}
    wipe_all() -> int
    delete_by_ids(ids) -> int
    export_all() -> list
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.memory.semantic import HashEmbeddingFn

log = logging.getLogger(__name__)

_PERSIST_DIR = Path.home() / ".aurabot" / "chromadb"
_COLLECTION  = "aurabot_memory"
_client      = None
_collection  = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection

    import chromadb
    _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    _client     = chromadb.PersistentClient(path=str(_PERSIST_DIR))
    _collection = _client.get_or_create_collection(
        name=_COLLECTION,
        embedding_function=HashEmbeddingFn(),
        metadata={"hnsw:space": "cosine"},
    )
    log.info("ChromaDB ready — %d documents in memory", _collection.count())
    return _collection


def add_turn(user_msg: str, bot_msg: str) -> str:
    """Persist one conversation turn. Returns the generated document ID."""
    col     = _get_collection()
    turn_id = f"turn_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    now     = datetime.now(timezone.utc)

    col.add(
        ids       =[turn_id],
        documents =[f"User: {user_msg}\nAuraBot: {bot_msg}"],
        metadatas =[{
            "user":      user_msg[:400],
            "bot":       bot_msg[:400],
            "timestamp": now.isoformat(),
            "date":      now.strftime("%Y-%m-%d"),
        }],
    )
    log.debug("Memory stored: %s", turn_id)
    return turn_id


def query_similar(text: str, n_results: int = 5) -> list:
    """Return the most semantically similar past turns to `text`."""
    col = _get_collection()
    if col.count() == 0:
        return []

    n       = min(n_results, col.count())
    results = col.query(
        query_texts=[text],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    out = []
    for i, doc_id in enumerate(results["ids"][0]):
        out.append({
            "id":       doc_id,
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": round(results["distances"][0][i], 4),
        })
    return out


def search_memory(query: str, n_results: int = 10) -> list:
    """Search memory for relevant entries (Settings -> Memory tab)."""
    return query_similar(query, n_results=n_results)


def get_stats() -> dict:
    """Return {"count": int, "last_date": str|None} for the Memory tab."""
    try:
        col   = _get_collection()
        count = col.count()
        if count == 0:
            return {"count": 0, "last_date": None}

        peek  = col.peek(limit=min(count, 500))
        dates = [m.get("date", "") for m in (peek.get("metadatas") or [])]
        valid = sorted([d for d in dates if d], reverse=True)
        return {"count": count, "last_date": valid[0] if valid else None}
    except Exception as exc:
        log.warning("Memory stats error: %s", exc)
        return {"count": 0, "last_date": None}


def wipe_all() -> int:
    """Delete all stored memory. Returns the number of deleted documents."""
    global _collection
    try:
        col   = _get_collection()
        count = col.count()
        if count > 0 and _client is not None:
            _client.delete_collection(_COLLECTION)
            _collection = None
        log.info("Memory wiped (%d documents deleted)", count)
        return count
    except Exception as exc:
        log.error("Memory wipe error: %s", exc)
        return 0


def delete_by_ids(ids: list) -> int:
    """Delete specific memory entries by ID. Returns count actually deleted."""
    if not ids:
        return 0
    try:
        col = _get_collection()
        col.delete(ids=ids)
        log.info("Deleted %d memory entries", len(ids))
        return len(ids)
    except Exception as exc:
        log.error("Memory delete error: %s", exc)
        return 0


def export_all() -> list:
    """Return all turns as a list of dicts for JSON export."""
    try:
        col = _get_collection()
        if col.count() == 0:
            return []
        result = col.get(include=["documents", "metadatas"])
        return [
            {"id": doc_id, "metadata": result["metadatas"][i]}
            for i, doc_id in enumerate(result["ids"])
        ]
    except Exception as exc:
        log.error("Memory export error: %s", exc)
        return []
