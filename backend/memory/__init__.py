"""AuraBot memory package.

Public API (re-exported from episodic.py for backward compat):
    add_turn, query_similar, search_memory, get_stats,
    wipe_all, delete_by_ids, export_all
"""

from backend.memory.episodic import (
    add_turn,
    query_similar,
    search_memory,
    get_stats,
    wipe_all,
    delete_by_ids,
    export_all,
)

__all__ = [
    "add_turn",
    "query_similar",
    "search_memory",
    "get_stats",
    "wipe_all",
    "delete_by_ids",
    "export_all",
]
