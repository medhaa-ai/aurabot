"""SerpAPI web search integration — Phase 3.

Uses only stdlib urllib so no extra packages are needed beyond what Phase 1 installed.
Falls back gracefully when no SerpAPI key is set.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"
TIMEOUT      = 10  # seconds


async def execute_search(query: str) -> str:
    """
    Run a web search via SerpAPI and return a plain-text summary Claude can use.
    Returns a human-readable string (not JSON) so Claude can cite it directly.
    Falls back to a helpful message when the key is absent or the call fails.
    """
    from backend.secure_store import get_secret

    api_key = get_secret("serpapi_key")
    if not api_key:
        return (
            "Web search is not configured. "
            "Add your SerpAPI key in Settings -> API Keys to enable live search. "
            "In the meantime, answer from your training knowledge and note the limitation."
        )

    try:
        return _call_serpapi(query, api_key)
    except Exception as exc:
        log.warning("SerpAPI error for query %r: %s", query, exc)
        return (
            f"Web search failed ({exc}). "
            "Please answer from training knowledge and note that live data is unavailable."
        )


def _call_serpapi(query: str, api_key: str) -> str:
    """Synchronous HTTP call — called from asyncio context via normal call (no blocking issue
    since FastAPI runs in a thread pool for sync I/O and claude_client awaits this directly)."""
    params = urllib.parse.urlencode({
        "q":       query,
        "api_key": api_key,
        "num":     5,
        "hl":      "en",
        "gl":      "in",  # India-biased results for Bengaluru context
    })
    url = f"{SERPAPI_BASE}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "AuraBot/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    return _format_results(query, raw)


def _format_results(query: str, raw: dict) -> str:
    """Convert SerpAPI JSON into a concise text block for Claude."""
    lines: list[str] = [f'Web search results for: "{query}"\n']

    # Answer box (featured snippet)
    if answer := raw.get("answer_box"):
        snippet = (
            answer.get("answer")
            or answer.get("snippet")
            or answer.get("result")
            or ""
        )
        if snippet:
            lines.append(f"[Featured answer] {snippet.strip()}")
            if link := answer.get("link"):
                lines.append(f"Source: {link}")
            lines.append("")

    # Organic results (top 5)
    for i, result in enumerate(raw.get("organic_results", [])[:5], 1):
        title   = result.get("title", "").strip()
        snippet = result.get("snippet", "").strip()
        link    = result.get("link", "")
        if title or snippet:
            lines.append(f"{i}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
            if link:
                lines.append(f"   {link}")
            lines.append("")

    if len(lines) <= 1:
        return f'No results found for "{query}". Answer from training knowledge.'

    return "\n".join(lines).strip()
