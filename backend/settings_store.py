"""Settings store — Phase 2.

Non-sensitive settings (name, timezone, theme, etc.) → plain JSON in settings.json.
Sensitive keys (API keys, OAuth secrets) → encrypted via secure_store.py.

The public API (load_settings / save_setting) handles routing transparently.
"""

import json
import logging
from pathlib import Path
from typing import Any

from backend.secure_store import SENSITIVE_KEYS, set_secret, get_secret, has_secret

log = logging.getLogger(__name__)

SETTINGS_PATH = Path.home() / ".aurabot" / "settings.json"

DEFAULTS: dict[str, Any] = {
    "user_name":       "Boss",
    "timezone":        "Asia/Kolkata",
    "theme":           "dark",
    "work_start":      "09:00",
    "work_end":        "19:00",
    "wake_time":       "07:00",
    "sleep_time":      "23:00",
    "greeting_style":  "casual",
}


# ── Plain settings (non-sensitive) ────────────────────────────────────────

def _load_plain() -> dict:
    if not SETTINGS_PATH.exists():
        return dict(DEFAULTS)
    try:
        stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return {**DEFAULTS, **stored}
    except Exception as exc:
        log.error("Failed to load settings.json: %s", exc)
        return dict(DEFAULTS)


def _save_plain(data: dict) -> None:
    # Never write sensitive keys to plain JSON
    clean = {k: v for k, v in data.items() if k not in SENSITIVE_KEYS}
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Public API ─────────────────────────────────────────────────────────────

def load_settings() -> dict[str, Any]:
    """Return all non-sensitive settings.
    Sensitive keys are represented as has_{key}: True/False (never the value itself).
    """
    plain = _load_plain()
    # Add presence indicators for sensitive keys
    for key in SENSITIVE_KEYS:
        plain[f"has_{key}"] = has_secret(key)
    return plain


def save_setting(key: str, value: Any) -> None:
    """Route to encrypted store for sensitive keys, plain JSON for the rest."""
    if key in SENSITIVE_KEYS:
        set_secret(key, str(value))
    else:
        plain = _load_plain()
        plain[key] = value
        _save_plain(plain)


def get_setting(key: str, default: Any = None) -> Any:
    """Get a single setting value (routes through secure_store for sensitive keys)."""
    if key in SENSITIVE_KEYS:
        return get_secret(key, default or "")
    return _load_plain().get(key, default)
