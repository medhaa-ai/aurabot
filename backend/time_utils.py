"""Timezone-aware time utilities using Python's built-in zoneinfo (3.9+)."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import logging

log = logging.getLogger(__name__)

DEFAULT_TZ = "Asia/Kolkata"


def get_tz(tz_name: str = DEFAULT_TZ) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        log.warning("Unknown timezone %r, falling back to %s", tz_name, DEFAULT_TZ)
        return ZoneInfo(DEFAULT_TZ)


def now_in(tz_name: str = DEFAULT_TZ) -> datetime:
    return datetime.now(tz=get_tz(tz_name))


def good_greeting(name: str = "Boss", tz_name: str = DEFAULT_TZ) -> str:
    hour = now_in(tz_name).hour
    if hour < 12:
        period = "morning"
    elif hour < 17:
        period = "afternoon"
    else:
        period = "evening"
    return f"Good {period}, {name}"


def utc_now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))
