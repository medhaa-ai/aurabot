"""Permissions system — Phase 2 full implementation.

Flow:
  1. Frontend (or backend logic) calls POST /permissions/check
     with {action_id, description}.
  2. If the action_id has an "always" grant -> {granted: true, needs_prompt: false}.
  3. Otherwise -> {granted: false, needs_prompt: true, action_id, description}.
  4. Frontend shows the inline permission dialog in chat.
  5. User chooses:
       - "Allow once"   -> no storage, one-time use (frontend resolves true).
       - "Allow always" -> POST /permissions/grant -> stored permanently.
       - "Deny"         -> POST /permissions/deny -> optionally stored.
  6. Settings -> Permissions tab: GET /permissions/list + DELETE /permissions/revoke/{id}.
"""

import json
import logging
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

PERMISSIONS_PATH = Path.home() / ".aurabot" / "permissions.json"
PermissionChoice = Literal["always", "once", "deny"]


# ── Storage helpers ────────────────────────────────────────────────────────

def _load() -> dict:
    if not PERMISSIONS_PATH.exists():
        return {}
    try:
        return json.loads(PERMISSIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    PERMISSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERMISSIONS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Core functions ─────────────────────────────────────────────────────────

def check_permission(action_id: str, description: str) -> dict:
    """
    Returns a dict that the /permissions/check endpoint sends to the frontend.
    If 'always' is stored -> {granted: true, needs_prompt: false}.
    Otherwise -> {granted: false, needs_prompt: true, action_id, description}.
    """
    data = _load()
    entry = data.get(action_id, {})
    choice = entry.get("choice")

    if choice == "always":
        return {
            "granted":      True,
            "needs_prompt": False,
            "action_id":    action_id,
            "description":  description,
            "choice":       "always",
        }

    return {
        "granted":      False,
        "needs_prompt": True,
        "action_id":    action_id,
        "description":  description,
    }


def grant_permission(action_id: str, description: str, choice: PermissionChoice) -> None:
    """Persist a permission choice. Only 'always' and 'deny' are stored persistently."""
    if choice == "once":
        return  # one-time grants are not stored

    data = _load()
    data[action_id] = {
        "choice":      choice,
        "description": description,
    }
    _save(data)
    log.info("Permission %s -> %s", action_id, choice)


def revoke_permission(action_id: str) -> bool:
    """Remove a stored permission. Returns True if it existed."""
    data = _load()
    existed = action_id in data
    if existed:
        del data[action_id]
        _save(data)
        log.info("Permission revoked: %s", action_id)
    return existed


def list_permissions() -> list[dict]:
    """Return all stored permissions (for the Settings -> Permissions tab)."""
    data = _load()
    return [
        {
            "action_id":   k,
            "choice":      v.get("choice", "unknown"),
            "description": v.get("description", k),
        }
        for k, v in data.items()
    ]


def has_permission(action_id: str) -> bool:
    """Quick check: returns True only if 'always' is stored."""
    return _load().get(action_id, {}).get("choice") == "always"
