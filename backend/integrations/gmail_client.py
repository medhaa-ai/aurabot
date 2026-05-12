"""Gmail integration — Phase 5.

OAuth2 read-only access to Gmail using Google's python client libraries.

Flow:
  1. User sets Google Client ID + Secret in Settings -> API Keys.
  2. Frontend calls GET /gmail/auth-url  -> opens URL in system browser.
  3. User authorises; Google redirects to http://localhost:8765/gmail/callback?code=...
  4. Backend exchanges code for tokens, stores them encrypted.
  5. Frontend polls GET /gmail/status until {"connected": true}.

Token storage: secure_store key "gmail_token" (Fernet-encrypted JSON).
"""

import json
import logging

log = logging.getLogger(__name__)

SCOPES       = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
REDIRECT_URI = "http://localhost:8765/gmail/callback"


def _client_config() -> dict:
    from backend.secure_store import get_secret
    client_id     = get_secret("google_client_id")
    client_secret = get_secret("google_client_secret")
    if not client_id or not client_secret:
        raise ValueError(
            "Google Client ID and Secret are not configured. "
            "Add them in Settings -> API Keys first."
        )
    return {
        "installed": {
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uris": [REDIRECT_URI],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
        }
    }


def get_auth_url() -> str:
    """Generate and return the Google OAuth authorisation URL."""
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def handle_callback(code: str) -> str:
    """Exchange authorisation code for tokens, store them, return user email."""
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)
    creds = flow.credentials

    email = None
    try:
        from googleapiclient.discovery import build
        svc   = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        info  = svc.userinfo().get().execute()
        email = info.get("email")
    except Exception as exc:
        log.warning("Could not fetch Gmail user info: %s", exc)

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri or "https://oauth2.googleapis.com/token",
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes or SCOPES),
        "email":         email,
    }
    from backend.secure_store import set_secret
    set_secret("gmail_token", json.dumps(token_data))
    log.info("Gmail token stored for: %s", email or "unknown")
    return email or "connected"


def _get_credentials():
    """Load credentials from storage, refreshing if expired. Returns None if absent."""
    from backend.secure_store import get_secret, set_secret
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest

    token_json = get_secret("gmail_token")
    if not token_json:
        return None

    data  = json.loads(token_json)
    creds = Credentials(
        token         = data.get("token"),
        refresh_token = data.get("refresh_token"),
        token_uri     = data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id     = data.get("client_id"),
        client_secret = data.get("client_secret"),
        scopes        = data.get("scopes", SCOPES),
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            data["token"] = creds.token
            set_secret("gmail_token", json.dumps(data))
        except Exception as exc:
            log.warning("Gmail token refresh failed: %s", exc)
            return None

    return creds


def get_status() -> dict:
    """Return {"connected": bool, "email": str|None}."""
    from backend.secure_store import get_secret
    token_json = get_secret("gmail_token")
    if not token_json:
        return {"connected": False, "email": None}
    try:
        data  = json.loads(token_json)
        email = data.get("email")
        return {"connected": True, "email": email}
    except Exception:
        return {"connected": False, "email": None}


def disconnect() -> None:
    """Remove stored Gmail token."""
    from backend.secure_store import delete_secret
    delete_secret("gmail_token")
    log.info("Gmail disconnected")


def fetch_unread(max_messages: int = 10) -> list:
    """
    Fetch recent unread inbox emails.
    Returns list of {id, subject, sender, snippet, date}.
    Returns [] if Gmail is not connected or the call fails.
    """
    creds = _get_credentials()
    if creds is None:
        return []

    try:
        from googleapiclient.discovery import build
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

        results  = svc.users().messages().list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=max_messages,
        ).execute()
        messages = results.get("messages", [])

        emails = []
        for msg in messages:
            detail  = svc.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            emails.append({
                "id":      msg["id"],
                "subject": headers.get("Subject", "(No subject)"),
                "sender":  headers.get("From",    "Unknown"),
                "snippet": detail.get("snippet",  ""),
                "date":    headers.get("Date",     ""),
            })
        return emails

    except Exception as exc:
        log.error("Gmail fetch error: %s", exc)
        return []


def format_emails_for_claude(emails: list) -> str:
    """Format email list as plain text for Claude to summarise."""
    if not emails:
        return "No unread emails found in inbox."

    lines = [f"Unread inbox emails ({len(emails)} found):\n"]
    for i, e in enumerate(emails, 1):
        lines.append(f"{i}. From:    {e['sender']}")
        lines.append(f"   Subject: {e['subject']}")
        lines.append(f"   Date:    {e['date']}")
        lines.append(f"   Preview: {e['snippet'][:250]}")
        lines.append("")

    return "\n".join(lines).strip()


async def execute_email_check(_input: dict) -> str:
    """Tool executor called from claude_client when Claude uses check_email."""
    status = get_status()
    if not status["connected"]:
        return (
            "Gmail is not connected. "
            "Ask the user to go to Settings -> API Keys and click 'Connect Gmail'."
        )
    emails = fetch_unread(max_messages=10)
    return format_emails_for_claude(emails)
