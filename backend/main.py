"""AuraBot FastAPI backend — Phase 7: reminders, scheduler, calendar."""

import sys
import os
import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the project root is on sys.path so `from backend.X import Y` works
# when this file is run directly as `python backend/main.py`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Allow Google OAuth to return broader scopes than requested (e.g. includes
# legacy readonly scopes alongside new modify/events scopes)
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

# ── Logging setup (before any imports that might log) ─────────────────────
AURABOT_DIR = Path.home() / ".aurabot"
AURABOT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = AURABOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "backend.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.root.addHandler(_handler)
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.stream.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None
logging.root.addHandler(_stdout_handler)
logging.root.setLevel(logging.INFO)

log = logging.getLogger("aurabot")

# ── FastAPI ────────────────────────────────────────────────────────────────
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.scheduler import start as start_scheduler
    start_scheduler()
    yield

app = FastAPI(title="AuraBot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Electron renders from file://, needs open CORS
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Lazy imports (so missing Phase N deps don't break Phase 1) ─────────────
def _try_import(module_name: str):
    try:
        return __import__(module_name)
    except ImportError:
        return None

# ── Request / Response models ──────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    expression: str = "idle"

class SettingRequest(BaseModel):
    key: str
    value: str

class PermissionCheckRequest(BaseModel):
    action_id:   str
    description: str

class PermissionGrantRequest(BaseModel):
    action_id:   str
    description: str
    choice:      str   # "always" | "once" | "deny"

class MemoryDeleteRequest(BaseModel):
    ids: list

class MemoryAddRequest(BaseModel):
    user: str
    bot:  str

class ReminderAddRequest(BaseModel):
    text:    str
    fire_at: str   # ISO 8601 datetime string

class DismissNudgeRequest(BaseModel):
    id: str

# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Phase 3: streaming Claude response via SSE."""
    log.info("Chat request: %s", req.message[:80])

    from backend.claude_client import stream_claude_response

    return StreamingResponse(
        stream_claude_response(req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/settings/get")
async def settings_get():
    from backend.settings_store import load_settings
    return load_settings()


@app.post("/settings/set")
async def settings_set(req: SettingRequest):
    from backend.settings_store import save_setting
    save_setting(req.key, req.value)
    return {"ok": True}


@app.get("/permissions/list")
async def permissions_list():
    from backend.permissions import list_permissions
    return list_permissions()


@app.post("/permissions/check")
async def permissions_check(req: PermissionCheckRequest):
    """
    Frontend calls this before performing any sensitive action.
    Returns {granted, needs_prompt, action_id, description}.
    """
    from backend.permissions import check_permission
    return check_permission(req.action_id, req.description)


@app.post("/permissions/grant")
async def permissions_grant(req: PermissionGrantRequest):
    """Frontend sends the user's choice after the permission dialog."""
    from backend.permissions import grant_permission
    if req.choice not in ("always", "once", "deny"):
        return JSONResponse(status_code=400, content={"error": "Invalid choice"})
    grant_permission(req.action_id, req.description, req.choice)  # type: ignore[arg-type]
    return {"ok": True, "choice": req.choice}


@app.post("/permissions/revoke/{action_id}")
async def permissions_revoke(action_id: str):
    from backend.permissions import revoke_permission
    existed = revoke_permission(action_id)
    return {"ok": True, "existed": existed}


@app.post("/memory/add")
async def memory_add(req: MemoryAddRequest):
    """Directly store a memory turn. Used by self-tests and future integrations."""
    from backend.memory_store import add_turn
    turn_id = add_turn(req.user, req.bot)
    return {"ok": True, "id": turn_id}


@app.get("/memory/stats")
async def memory_stats():
    """Phase 4: return memory count and last entry date."""
    from backend.memory_store import get_stats
    return get_stats()


@app.get("/memory/search")
async def memory_search(q: str = ""):
    """Phase 4: search memory by query string."""
    if not q.strip():
        return []
    from backend.memory_store import search_memory
    return search_memory(q.strip(), n_results=10)


@app.post("/memory/wipe")
async def memory_wipe():
    """Phase 4: delete all stored memory."""
    from backend.memory_store import wipe_all
    deleted = wipe_all()
    return {"ok": True, "deleted": deleted}


@app.get("/memory/export")
async def memory_export():
    """Phase 4: export all memory as JSON."""
    from backend.memory_store import export_all
    return export_all()


@app.post("/memory/delete")
async def memory_delete(req: MemoryDeleteRequest):
    """Phase 4: delete specific memory entries by ID."""
    from backend.memory_store import delete_by_ids
    deleted = delete_by_ids(req.ids)
    return {"ok": True, "deleted": deleted}


@app.get("/gmail/auth-url")
async def gmail_auth_url():
    """Phase 5: return the Google OAuth URL to open in the user's browser."""
    try:
        from backend.integrations.gmail import get_auth_url
        return {"url": get_auth_url()}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/gmail/callback")
async def gmail_callback(code: str = "", error: str = ""):
    """Phase 5: Google redirects here after the user grants permission."""
    from fastapi.responses import HTMLResponse
    if error:
        html = f"""<!DOCTYPE html><html><head><title>AuraBot - Gmail</title>
<style>body{{font-family:sans-serif;background:#0F1729;color:#E8EEF8;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.box{{text-align:center;padding:40px;background:#1A2540;border-radius:16px;max-width:400px;}}</style></head>
<body><div class="box"><h2>Access Denied</h2><p>{error}</p><p>Close this tab and try again.</p></div></body></html>"""
        return HTMLResponse(content=html, status_code=400)

    if not code:
        return HTMLResponse(content="<p>Missing code parameter.</p>", status_code=400)

    try:
        from backend.integrations.gmail import handle_callback
        email = handle_callback(code)
        html = f"""<!DOCTYPE html><html><head><title>AuraBot - Gmail Connected</title>
<style>body{{font-family:sans-serif;background:#0F1729;color:#E8EEF8;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.box{{text-align:center;padding:40px;background:#1A2540;border-radius:16px;max-width:420px;}}
h2{{color:#A7C7E7;margin-bottom:8px;}} .email{{color:#6A9EC7;font-size:0.9em;margin:8px 0 20px;}}
.note{{color:#8899BB;font-size:0.85em;line-height:1.6;}}</style></head>
<body><div class="box"><h2>Gmail Connected!</h2>
<p class="email">{email}</p>
<p class="note">You can close this tab and return to AuraBot.<br>
AuraBot can now read your inbox when you ask about emails.</p></div></body></html>"""
        return HTMLResponse(content=html)
    except Exception as exc:
        log.error("Gmail callback error: %s", exc, exc_info=True)
        html = f"""<!DOCTYPE html><html><head><title>AuraBot - Error</title>
<style>body{{font-family:sans-serif;background:#0F1729;color:#E8EEF8;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.box{{text-align:center;padding:40px;background:#1A2540;border-radius:16px;}}</style></head>
<body><div class="box"><h2>Connection Failed</h2><p>{exc}</p><p>Close this tab and try again from Settings.</p></div></body></html>"""
        return HTMLResponse(content=html, status_code=500)


@app.get("/gmail/status")
async def gmail_status():
    """Phase 5: return Gmail connection status."""
    from backend.integrations.gmail import get_status
    return get_status()


@app.get("/gmail/unread")
async def gmail_unread(max_messages: int = 10):
    """Phase 5: fetch unread emails."""
    from backend.integrations.gmail import fetch_unread
    return fetch_unread(max_messages=max_messages)


@app.post("/gmail/disconnect")
async def gmail_disconnect():
    """Phase 5: remove stored Gmail token."""
    from backend.integrations.gmail import disconnect
    disconnect()
    return {"ok": True}


@app.post("/whatsapp/start")
async def whatsapp_start():
    """Phase 6: start the Node.js WhatsApp bridge process."""
    from backend.integrations.whatsapp import start_bridge
    return start_bridge()


@app.get("/whatsapp/status")
async def whatsapp_status():
    """Phase 6: return bridge + WhatsApp connection status."""
    from backend.integrations.whatsapp import get_status
    return get_status()


@app.get("/whatsapp/qr")
async def whatsapp_qr():
    """Phase 6: return current QR code from the bridge."""
    from backend.integrations.whatsapp import get_qr
    return get_qr()


@app.get("/whatsapp/chats")
async def whatsapp_chats():
    """Phase 6: return recent WhatsApp chats."""
    from backend.integrations.whatsapp import get_status, get_chats
    if not get_status()["connected"]:
        return JSONResponse(status_code=503, content={"error": "WhatsApp not connected"})
    return get_chats()


@app.post("/whatsapp/disconnect")
async def whatsapp_disconnect():
    """Phase 6: stop the WhatsApp bridge."""
    from backend.integrations.whatsapp import stop_bridge
    return stop_bridge()


@app.post("/reminders/add")
async def reminders_add(req: ReminderAddRequest):
    """Phase 7: add a new reminder."""
    from backend.reminder_store import add_reminder
    rid = add_reminder(req.text, req.fire_at)
    return {"ok": True, "id": rid}


@app.get("/reminders/list")
async def reminders_list():
    """Phase 7: return unfired reminders."""
    from backend.reminder_store import list_reminders
    return list_reminders()


@app.delete("/reminders/{rid}")
async def reminders_delete(rid: str):
    """Phase 7: delete a reminder by id."""
    from backend.reminder_store import delete_reminder
    found = delete_reminder(rid)
    return {"ok": True, "found": found}


@app.get("/nudges/pending")
async def nudges_pending():
    """Phase 7: fire any due reminders then return all pending nudges."""
    from backend.reminder_store import check_and_fire, get_pending_nudges
    check_and_fire()
    return get_pending_nudges()


@app.post("/nudges/dismiss")
async def nudges_dismiss(req: DismissNudgeRequest):
    """Phase 7: dismiss a nudge by id."""
    from backend.reminder_store import dismiss_nudge
    found = dismiss_nudge(req.id)
    return {"ok": True, "found": found}


@app.post("/nudges/dismiss-all")
async def nudges_dismiss_all():
    """Phase 7: clear all pending nudges."""
    from backend.reminder_store import dismiss_all_nudges
    count = dismiss_all_nudges()
    return {"ok": True, "dismissed": count}


@app.get("/calendar/status")
async def calendar_status():
    """Phase 7: return Calendar connection status."""
    from backend.integrations.calendar import get_status
    return get_status()


@app.get("/calendar/auth-url")
async def calendar_auth_url():
    """Phase 7: return OAuth URL for Gmail + Calendar combined auth."""
    try:
        from backend.integrations.calendar import get_auth_url
        return {"url": get_auth_url()}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/calendar/events")
async def calendar_events(max_events: int = 10):
    """Phase 7: fetch upcoming calendar events."""
    from backend.integrations.calendar import get_upcoming_events
    return get_upcoming_events(max_events=max_events)


@app.get("/secrets/status")
async def secrets_status():
    """Return which API keys are currently stored (never the values)."""
    from backend.secure_store import has_secret, SENSITIVE_KEYS
    return {key: has_secret(key) for key in SENSITIVE_KEYS}


# ── Global error handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    log.info("Starting AuraBot backend on 127.0.0.1:8765")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info",
    )
