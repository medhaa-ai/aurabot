"""Backward-compat shim — real implementation lives in backend/memory/."""

from backend.memory import (  # noqa: F401
    add_turn,
    query_similar,
    search_memory,
    get_stats,
    wipe_all,
    delete_by_ids,
    export_all,
)
