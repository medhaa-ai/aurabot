"""In-process short-term conversation buffer.

Holds the last N turns in memory for immediate context injection.
Not persisted — clears on backend restart.
"""

from collections import deque

_MAX_TURNS = 20
_buffer: deque = deque(maxlen=_MAX_TURNS)


def push(user_msg: str, bot_msg: str) -> None:
    """Append a turn to the short-term buffer."""
    _buffer.append({"user": user_msg, "bot": bot_msg})


def get_recent(n: int = 5) -> list:
    """Return the n most recent turns as [{"user": ..., "bot": ...}]."""
    items = list(_buffer)
    return items[-n:] if len(items) > n else items


def clear() -> None:
    """Clear the buffer (e.g. on explicit memory wipe)."""
    _buffer.clear()
