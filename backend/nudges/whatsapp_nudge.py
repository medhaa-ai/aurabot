"""Periodic WhatsApp unread-message nudge checker.

Called from the scheduler every 30 s; internally throttles to fire at most
once per 35 minutes so the user gets reminded without being spammed.
"""

import logging
import time

log = logging.getLogger(__name__)

_INTERVAL_SEC   = 35 * 60          # 35-minute gap between nudges
_last_fired: float = 0.0
_last_unread_ids: set = set()       # track which chats we've already nudged


def check_whatsapp_nudges() -> None:
    global _last_fired, _last_unread_ids

    if time.time() - _last_fired < _INTERVAL_SEC:
        return

    try:
        from backend.integrations.whatsapp import get_status, get_unread_chats
        status = get_status()
        if not status.get("bridge_running") or not status.get("connected"):
            return

        unread = get_unread_chats()
        if not unread:
            _last_unread_ids = set()
            return

        # Only fire if there are NEW chats with unread messages since last check
        current_ids = {c.get("id", c.get("name", "")) for c in unread}
        new_ids = current_ids - _last_unread_ids
        if not new_ids and _last_fired > 0:
            return

        _last_fired      = time.time()
        _last_unread_ids = current_ids

        total   = sum(c.get("unreadCount", 0) for c in unread)
        names   = [c.get("name", "Unknown") for c in unread[:3]]
        summary = ", ".join(names)
        if len(unread) > 3:
            summary += f" +{len(unread) - 3} more"

        from backend.reminder_store import add_nudge
        add_nudge(
            text      = f"{total} unread WhatsApp {'message' if total == 1 else 'messages'} from {summary}",
            urgency   = "high",
            nudge_type = "whatsapp",
        )
        log.info("WhatsApp nudge fired — %d unread from %d chats", total, len(unread))

    except Exception as exc:
        log.debug("WhatsApp nudge check error: %s", exc)
