"""WhatsApp bridge integration — Phase 6.

Manages the Node.js whatsapp-web.js bridge process (port 8766).
Proxies read-only API calls to the bridge and provides a Claude tool executor.

Bridge lifecycle:
  - Started on demand when user clicks "Start WhatsApp" in Settings.
  - Bridge persists its session at ~/.aurabot/whatsapp/ (LocalAuth).
  - Python proxies all calls to http://127.0.0.1:8766.
"""

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

BRIDGE_PORT = 8766
BRIDGE_URL  = f"http://127.0.0.1:{BRIDGE_PORT}"

def _find_bridge_dir() -> Path:
    # 1. Electron sets this env var explicitly — trust it first
    env_dir = os.environ.get("AURABOT_BRIDGE_DIR", "").strip()
    if env_dir:
        p = Path(env_dir)
        log.info("WhatsApp bridge dir from env: %s", p)
        return p

    here = Path(__file__).resolve()
    # 2. Packaged layout: .../resources/app/backend/integrations/whatsapp.py
    #    → go 4 levels up to reach resources/, then down to whatsapp_bridge/
    packaged = here.parent.parent.parent.parent / "whatsapp_bridge"
    if packaged.exists():
        log.info("WhatsApp bridge dir (packaged fallback): %s", packaged)
        return packaged

    # 3. Dev layout: project_root/backend/integrations/whatsapp.py
    #    → 3 levels up is project root
    dev = here.parent.parent.parent / "whatsapp_bridge"
    log.info("WhatsApp bridge dir (dev fallback): %s", dev)
    return dev

BRIDGE_DIR = _find_bridge_dir()

_bridge_proc: "subprocess.Popen | None" = None


# ── Process management ─────────────────────────────────────────────────────

def _bridge_alive() -> bool:
    try:
        with urllib.request.urlopen(f"{BRIDGE_URL}/wa/status", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start_bridge() -> dict:
    """Start the Node.js bridge if not already running. Returns {started, message}."""
    global _bridge_proc

    if _bridge_alive():
        return {"started": False, "message": "Bridge already running"}

    bridge_script = BRIDGE_DIR / "bridge.js"
    if not bridge_script.exists():
        return {"started": False, "message": f"Bridge script not found: {bridge_script}"}

    if not (BRIDGE_DIR / "node_modules").exists():
        return {
            "started": False,
            "message": "Run 'npm install' in the whatsapp_bridge/ folder first.",
        }

    try:
        _bridge_proc = subprocess.Popen(
            ["node", str(bridge_script)],
            cwd=str(BRIDGE_DIR),
            env={**os.environ},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log.info("WhatsApp bridge started (PID %s)", _bridge_proc.pid)
    except FileNotFoundError:
        return {"started": False, "message": "Node.js not found. Install Node.js first."}
    except Exception as exc:
        return {"started": False, "message": str(exc)}

    for _ in range(20):
        time.sleep(0.5)
        if _bridge_alive():
            return {"started": True, "message": "Bridge started — scan the QR code to connect"}

    return {"started": True, "message": "Bridge starting — QR code will appear shortly"}


def stop_bridge() -> dict:
    """Stop the Node.js bridge process."""
    global _bridge_proc
    try:
        _proxy_post("/wa/disconnect")
    except Exception:
        pass

    if _bridge_proc and _bridge_proc.poll() is None:
        _bridge_proc.terminate()
        try:
            _bridge_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _bridge_proc.kill()
        _bridge_proc = None
        log.info("WhatsApp bridge stopped")

    return {"ok": True}


# ── Bridge HTTP proxy ──────────────────────────────────────────────────────

def _proxy_get(path: str, timeout: int = 8):
    url = f"{BRIDGE_URL}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def _proxy_post(path: str, body: dict = None, timeout: int = 8) -> dict:
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(
        f"{BRIDGE_URL}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ── Public API ─────────────────────────────────────────────────────────────

def get_status() -> dict:
    """Return bridge + WhatsApp connection status."""
    if not _bridge_alive():
        return {"bridge_running": False, "connected": False, "name": None, "phone": None}
    try:
        data = _proxy_get("/wa/status")
        return {
            "bridge_running": True,
            "connected":      data.get("connected", False),
            "name":           data.get("name"),
            "phone":          data.get("phone"),
        }
    except Exception as exc:
        log.warning("WhatsApp status error: %s", exc)
        return {"bridge_running": False, "connected": False, "name": None, "phone": None}


def get_qr() -> dict:
    """Return QR code state from the bridge."""
    if not _bridge_alive():
        return {"connected": False, "qr": None, "initialising": False}
    try:
        return _proxy_get("/wa/qr")
    except Exception:
        return {"connected": False, "qr": None, "initialising": False}


def get_chats(limit: int = 100) -> list:
    """Return up to `limit` most recent chats (default 100)."""
    if not _bridge_alive():
        return []
    try:
        return _proxy_get(f"/wa/chats?limit={limit}")
    except Exception as exc:
        log.warning("WhatsApp chats error: %s", exc)
        return []


def get_recent_chats_with_messages(chat_limit: int = 25, msg_limit: int = 15) -> list:
    """
    Return the most recent `chat_limit` chats, each with their last
    `msg_limit` messages. Covers both read and unread conversations.
    """
    if not _bridge_alive():
        return []
    try:
        return _proxy_get(
            f"/wa/recent?chats={chat_limit}&messages={msg_limit}",
            timeout=30,
        )
    except Exception as exc:
        log.warning("WhatsApp recent chats error: %s", exc)
        return []


def get_unread_chats() -> list:
    """
    Return all chats with unread messages, scanning the full chat list.
    Each chat includes a `messages` list with recent message bodies for context.
    """
    if not _bridge_alive():
        return []
    try:
        return _proxy_get("/wa/unread", timeout=20)
    except Exception as exc:
        log.warning("WhatsApp unread chats error: %s", exc)
        return []


def disconnect() -> None:
    """Disconnect and stop the bridge."""
    stop_bridge()
    log.info("WhatsApp disconnected")


def format_chats_for_claude(chats: list) -> str:
    """Format recent chats as plain text for Claude to summarise."""
    if not chats:
        return "No WhatsApp chats found."

    lines = [f"Recent WhatsApp chats ({len(chats)} shown):\n"]
    for i, c in enumerate(chats, 1):
        name       = c.get("name", "Unknown")
        unread     = c.get("unreadCount", 0)
        preview    = (c.get("lastMessage") or "")[:200]
        group_tag  = " (group)" if c.get("isGroup") else ""
        unread_str = f" [{unread} unread]" if unread else ""
        lines.append(f"{i}. {name}{group_tag}{unread_str}")
        if preview:
            lines.append(f"   Last: {preview}")
        lines.append("")

    return "\n".join(lines).strip()


def format_unread_for_claude(chats: list) -> str:
    """Format unread chats with message context for Claude."""
    if not chats:
        return "No unread WhatsApp messages."

    from datetime import datetime
    lines = [f"Unread WhatsApp messages ({len(chats)} conversation{'s' if len(chats) != 1 else ''}):\n"]
    for i, c in enumerate(chats, 1):
        name      = c.get("name", "Unknown")
        unread    = c.get("unreadCount", 0)
        group_tag = " (group)" if c.get("isGroup") else ""
        lines.append(f"{i}. {name}{group_tag} — {unread} unread")

        messages = c.get("messages", [])
        if messages:
            for m in messages:
                if not m.get("body") or m.get("type") not in (None, "chat", ""):
                    continue
                ts = m.get("timestamp", 0)
                try:
                    t = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
                except Exception:
                    t = ""
                prefix = "   You:" if m.get("fromMe") else f"   {name.split()[0]}:"
                lines.append(f"{prefix} [{t}] {m['body'][:250]}")
        elif c.get("lastMessage"):
            lines.append(f"   Last: {c['lastMessage'][:200]}")

        lines.append("")

    return "\n".join(lines).strip()


def _fmt_messages(chat_name: str, messages: list) -> list:
    """Render a message list as indented lines."""
    from datetime import datetime
    lines = []
    for m in messages:
        if not m.get("body") or m.get("type") not in (None, "chat", ""):
            continue
        ts = m.get("timestamp", 0)
        try:
            t = datetime.fromtimestamp(ts).strftime("%d %b %H:%M") if ts else ""
        except Exception:
            t = ""
        prefix = "   You" if m.get("fromMe") else f"   {chat_name.split()[0]}"
        lines.append(f"{prefix} [{t}]: {m['body'][:400]}")
    return lines


async def execute_whatsapp_check(_input: dict) -> str:
    """Tool executor called from claude_client when Claude uses check_whatsapp."""
    status = get_status()
    if not status["bridge_running"]:
        return (
            "WhatsApp is not running. "
            "Ask the user to go to Settings -> API Keys, "
            "click 'Start WhatsApp', and scan the QR code with their phone."
        )
    if not status["connected"]:
        return (
            "WhatsApp bridge is running but the phone has not scanned the QR code yet. "
            "Please scan the QR code shown in Settings -> API Keys."
        )

    # Fetch last 25 chats with full message history (read + unread)
    recent = get_recent_chats_with_messages(chat_limit=25, msg_limit=15)
    if not recent:
        return "No WhatsApp chats found."

    from datetime import datetime
    lines = [f"WhatsApp — last {len(recent)} conversations:\n"]
    for i, c in enumerate(recent, 1):
        name      = c.get("name", "Unknown")
        unread    = c.get("unreadCount", 0)
        group_tag = " (group)" if c.get("isGroup") else ""
        unread_str = f"  *** {unread} UNREAD ***" if unread else ""
        lines.append(f"{i}. {name}{group_tag}{unread_str}")
        msg_lines = _fmt_messages(name, c.get("messages", []))
        lines.extend(msg_lines if msg_lines else ["   (no text messages)"])
        lines.append("")

    return "\n".join(lines).strip()
