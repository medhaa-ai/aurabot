"""Daily motivational nudge logic — fires at work_start and work_end."""

import logging
import random

from backend.nudges.quotes import MORNING_LINES, EVENING_LINES

log = logging.getLogger(__name__)

_last_morning_date: "str | None" = None
_last_evening_date: "str | None" = None


def _today_local() -> str:
    try:
        from backend.settings_store import get_setting
        from backend.time_utils import now_in
        return now_in(get_setting("timezone", "Asia/Kolkata")).strftime("%Y-%m-%d")
    except Exception:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")


def _now_hm() -> tuple:
    try:
        from backend.settings_store import get_setting
        from backend.time_utils import now_in
        t = now_in(get_setting("timezone", "Asia/Kolkata"))
        return t.hour, t.minute
    except Exception:
        from datetime import datetime
        t = datetime.now()
        return t.hour, t.minute


def _parse_hm(hhmm: str) -> tuple:
    try:
        h, m = hhmm.split(":")
        return int(h), int(m)
    except Exception:
        return 9, 0


def check_daily_nudges() -> None:
    """Fire morning and evening motivation nudges at the configured work hours."""
    global _last_morning_date, _last_evening_date
    from backend.settings_store import get_setting
    from backend.reminder_store import add_nudge

    today = _today_local()
    h, m  = _now_hm()
    name  = get_setting("user_name", "there")

    work_start = get_setting("work_start", "09:00")
    ws_h, ws_m = _parse_hm(work_start)
    if h == ws_h and 0 <= (m - ws_m) < 5 and _last_morning_date != today:
        _last_morning_date = today
        msg = random.choice(MORNING_LINES)
        add_nudge(f"{msg} ({work_start} — go get it, {name}!)", urgency="low", nudge_type="motivation")
        log.info("Morning nudge fired")

    work_end   = get_setting("work_end", "19:00")
    we_h, we_m = _parse_hm(work_end)
    if h == we_h and 0 <= (m - we_m) < 5 and _last_evening_date != today:
        _last_evening_date = today
        msg = random.choice(EVENING_LINES)
        add_nudge(msg, urgency="low", nudge_type="motivation")
        log.info("Evening nudge fired")
