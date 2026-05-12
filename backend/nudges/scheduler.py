"""Background scheduler daemon — fires due reminders and daily nudges.

Start once at app startup by calling start().
"""

import logging
import threading
import time

log = logging.getLogger(__name__)

_started = False


def _run() -> None:
    log.info("Scheduler running")
    while True:
        try:
            from backend.reminder_store import check_and_fire
            check_and_fire()
        except Exception as exc:
            log.debug("Scheduler reminder error: %s", exc)
        try:
            from backend.nudges.motivational import check_daily_nudges
            check_daily_nudges()
        except Exception as exc:
            log.debug("Scheduler daily nudge error: %s", exc)
        try:
            from backend.nudges.whatsapp_nudge import check_whatsapp_nudges
            check_whatsapp_nudges()
        except Exception as exc:
            log.debug("Scheduler WhatsApp nudge error: %s", exc)
        time.sleep(30)


def start() -> None:
    """Start the scheduler daemon thread. Safe to call multiple times."""
    global _started
    if _started:
        return
    _started = True
    t = threading.Thread(target=_run, daemon=True, name="aurabot-scheduler")
    t.start()
    log.info("Scheduler daemon started")
