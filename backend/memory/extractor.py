"""Fact extractor — identifies and tags noteworthy facts from conversation turns.

Currently a lightweight heuristic pass. Future: Claude-assisted extraction.
"""

import re

_FACT_PATTERNS = [
    re.compile(r"\bmy name is\b", re.I),
    re.compile(r"\bi (work|live|am based)\b", re.I),
    re.compile(r"\bremind me\b", re.I),
    re.compile(r"\bi prefer\b", re.I),
    re.compile(r"\bi (hate|love|like|dislike)\b", re.I),
]


def is_notable(text: str) -> bool:
    """Return True if the text likely contains a personal fact worth storing."""
    return any(p.search(text) for p in _FACT_PATTERNS)


def extract_tags(text: str) -> list:
    """Return simple string tags for a piece of text (used for filtering)."""
    tags = []
    t = text.lower()
    if "email" in t or "gmail" in t:
        tags.append("email")
    if "calendar" in t or "meeting" in t or "schedule" in t:
        tags.append("calendar")
    if "whatsapp" in t or "message" in t:
        tags.append("messaging")
    if "remind" in t or "reminder" in t:
        tags.append("reminder")
    return tags
