"""Google Calendar integration — Phase 7.

Read-only access using the same OAuth credentials as Gmail.
To get Calendar access, the user clicks "Connect Calendar" which re-authorises
with both gmail.readonly + calendar.readonly scopes. This overwrites the stored
gmail_token with credentials valid for both.
"""

import json
import logging

log = logging.getLogger(__name__)

CALENDAR_SCOPE  = "https://www.googleapis.com/auth/calendar.events"
COMBINED_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    CALENDAR_SCOPE,
]


def get_status() -> dict:
    """Return {connected: bool} — True if calendar scope is in stored token."""
    from backend.secure_store import get_secret
    token_json = get_secret("gmail_token")
    if not token_json:
        return {"connected": False}
    try:
        data   = json.loads(token_json)
        scopes = data.get("scopes", [])
        return {"connected": any("calendar" in s for s in scopes)}
    except Exception:
        return {"connected": False}


def get_auth_url() -> str:
    """Generate OAuth URL requesting Gmail + Calendar scopes (combined auth)."""
    from google_auth_oauthlib.flow import Flow
    from backend.integrations.gmail_client import _client_config, REDIRECT_URI
    flow = Flow.from_client_config(_client_config(), scopes=COMBINED_SCOPES)
    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def get_upcoming_events(max_events: int = 10) -> list:
    """Fetch upcoming events from the user's primary calendar."""
    from backend.integrations.gmail_client import _get_credentials
    creds = _get_credentials()
    if creds is None:
        return []
    try:
        from datetime import datetime, timezone
        from googleapiclient.discovery import build
        svc    = build("calendar", "v3", credentials=creds, cache_discovery=False)
        now    = datetime.now(timezone.utc).isoformat()
        result = svc.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_events,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        return [
            {
                "id":       e.get("id", ""),
                "summary":  e.get("summary", "(No title)"),
                "start":    (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date", ""),
                "end":      (e.get("end")   or {}).get("dateTime") or (e.get("end")   or {}).get("date", ""),
                "location": e.get("location", ""),
            }
            for e in events
        ]
    except Exception as exc:
        log.error("Calendar fetch error: %s", exc)
        return []


def create_event(summary: str, start: str, end: str,
                 description: str = "", location: str = "",
                 timezone: str = "Asia/Kolkata") -> dict:
    """
    Create a Google Calendar event.
    start/end: ISO 8601 strings e.g. '2026-05-12T15:00:00+05:30'
    Returns {"ok": True, "event_id": ..., "link": ...} or {"ok": False, "error": ...}
    """
    from backend.integrations.gmail_client import _get_credentials
    creds = _get_credentials()
    if creds is None:
        return {"ok": False, "error": "Google not connected"}
    try:
        from googleapiclient.discovery import build
        svc   = build("calendar", "v3", credentials=creds, cache_discovery=False)
        body  = {
            "summary":     summary,
            "description": description,
            "location":    location,
            "start":       {"dateTime": start, "timeZone": timezone},
            "end":         {"dateTime": end,   "timeZone": timezone},
        }
        event = svc.events().insert(calendarId="primary", body=body).execute()
        log.info("Calendar event created: %s", event.get("id"))
        return {
            "ok":       True,
            "event_id": event.get("id", ""),
            "link":     event.get("htmlLink", ""),
            "summary":  event.get("summary", summary),
        }
    except Exception as exc:
        log.error("Calendar create event error: %s", exc)
        return {"ok": False, "error": str(exc)}


def format_events_for_claude(events: list) -> str:
    if not events:
        return "No upcoming calendar events found."

    lines = [f"Upcoming calendar events ({len(events)} found):\n"]
    for i, e in enumerate(events, 1):
        start = e.get("start", "")
        if "T" in start:
            try:
                from datetime import datetime
                dt    = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start = dt.strftime("%a %d %b, %I:%M %p")
            except Exception:
                pass
        lines.append(f"{i}. {e.get('summary', '(No title)')}")
        if start:
            lines.append(f"   When:  {start}")
        if e.get("location"):
            lines.append(f"   Where: {e['location']}")
        lines.append("")

    return "\n".join(lines).strip()


async def execute_calendar_check(_input: dict) -> str:
    """Tool executor called from claude_client when Claude uses check_calendar."""
    if not get_status()["connected"]:
        return (
            "Google Calendar is not connected. "
            "Ask the user to go to Settings -> API Keys and click 'Connect Calendar'."
        )
    events = get_upcoming_events(max_events=10)
    return format_events_for_claude(events)
