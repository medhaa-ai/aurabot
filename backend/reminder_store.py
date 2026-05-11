"""Reminder store — Phase 7.

JSON persistence for reminders and pending nudges.
File: ~/.aurabot/reminders.json

Lifecycle:
  - Claude calls set_reminder tool -> add_reminder() stores it
  - Scheduler / /nudges/pending endpoint calls check_and_fire() each tick
  - Fired reminders become nudge entries until the frontend dismisses them
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_STORE = Path.home() / ".aurabot" / "reminders.json"
_STORE.parent.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    try:
        if _STORE.exists():
            return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to load reminders: %s", exc)
    return {"reminders": [], "nudges": []}


def _save(data: dict) -> None:
    try:
        _STORE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.error("Failed to save reminders: %s", exc)


# ── Reminders ──────────────────────────────────────────────────────────────

def add_reminder(text: str, fire_at_iso: str) -> str:
    """Store a reminder. Returns the new reminder id."""
    data = _load()
    rid  = str(uuid.uuid4())[:8]
    data.setdefault("reminders", []).append({
        "id":      rid,
        "text":    text,
        "fire_at": fire_at_iso,
        "fired":   False,
        "created": datetime.now(timezone.utc).isoformat(),
    })
    _save(data)
    log.info("Reminder added [%s]: %s at %s", rid, text[:60], fire_at_iso)
    return rid


def list_reminders() -> list:
    """Return unfired reminders sorted by fire time."""
    data = _load()
    pending = [r for r in data.get("reminders", []) if not r.get("fired")]
    return sorted(pending, key=lambda r: r.get("fire_at", ""))


def delete_reminder(rid: str) -> bool:
    """Delete a reminder by id. Returns True if found and removed."""
    data   = _load()
    before = len(data.get("reminders", []))
    data["reminders"] = [r for r in data.get("reminders", []) if r["id"] != rid]
    if len(data["reminders"]) < before:
        _save(data)
        return True
    return False


def check_and_fire() -> list:
    """Scan reminders, move due ones to nudges. Returns list of new nudge ids."""
    data       = _load()
    now        = datetime.now(timezone.utc)
    new_nudges = []

    for r in data.get("reminders", []):
        if r.get("fired"):
            continue
        try:
            fire_dt = datetime.fromisoformat(r["fire_at"].replace("Z", "+00:00"))
            if fire_dt.tzinfo is None:
                fire_dt = fire_dt.replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            continue

        if fire_dt <= now:
            r["fired"] = True
            nid = str(uuid.uuid4())[:8]
            data.setdefault("nudges", []).append({
                "id":      nid,
                "text":    f"Reminder: {r['text']}",
                "urgency": "high",
                "type":    "reminder",
            })
            new_nudges.append(nid)
            log.info("Reminder fired [%s]: %s", r["id"], r["text"][:60])

    if new_nudges:
        _save(data)
    return new_nudges


# ── Nudges ─────────────────────────────────────────────────────────────────

def add_nudge(text: str, urgency: str = "low", nudge_type: str = "system") -> str:
    """Add a nudge directly (used by scheduler for daily motivation)."""
    data = _load()
    nid  = str(uuid.uuid4())[:8]
    data.setdefault("nudges", []).append({
        "id":      nid,
        "text":    text,
        "urgency": urgency,
        "type":    nudge_type,
    })
    _save(data)
    return nid


def get_pending_nudges() -> list:
    """Return all undismissed nudges."""
    return _load().get("nudges", [])


def dismiss_nudge(nid: str) -> bool:
    """Remove a nudge by id. Returns True if found."""
    data   = _load()
    before = len(data.get("nudges", []))
    data["nudges"] = [n for n in data.get("nudges", []) if n["id"] != nid]
    if len(data["nudges"]) < before:
        _save(data)
        return True
    return False


def dismiss_all_nudges() -> int:
    """Clear all pending nudges. Returns count removed."""
    data  = _load()
    count = len(data.get("nudges", []))
    data["nudges"] = []
    _save(data)
    return count


# ── Claude tool executor ───────────────────────────────────────────────────

async def execute_reminder_set(tool_input: dict) -> str:
    """Called from claude_client when Claude uses the set_reminder tool."""
    text    = (tool_input.get("text") or "").strip()
    fire_at = (tool_input.get("when") or "").strip()

    if not text:
        return "Could not set reminder: no reminder text provided."
    if not fire_at:
        return "Could not set reminder: no time specified."

    try:
        dt  = datetime.fromisoformat(fire_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        rid = add_reminder(text, dt.isoformat())

        from backend.settings_store import get_setting
        from backend.time_utils import get_tz
        tz       = get_setting("timezone", "Asia/Kolkata")
        local_dt = dt.astimezone(get_tz(tz))
        time_str = local_dt.strftime("%A, %d %B at %I:%M %p")
        return f"Done! I'll remind you to '{text}' on {time_str}. (ID: {rid})"

    except ValueError as exc:
        return (
            f"Couldn't parse the time '{fire_at}'. "
            f"Please try a clearer format like '2026-05-09T15:00:00+05:30'. Detail: {exc}"
        )
    except Exception as exc:
        return f"Failed to set reminder: {exc}"
