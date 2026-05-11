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
    # Electron sets this env var to the exact path — always trust it if present
    if os.environ.get("AURABOT_BRIDGE_DIR"):
        return Path(os.environ["AURABOT_BRIDGE_DIR"])
    # Dev fallback: three levels up from this file is the project root
    return Path(__file__).resolve().parent.parent.parent / "whatsapp_bridge"

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


def get_chats() -> list:
    """Return up to 20 most recent chats."""
    if not _bridge_alive():
        return []
    try:
        return _proxy_get("/wa/chats")
    except Exception as exc:
        log.warning("WhatsApp chats error: %s", exc)
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
        name      = c.get("name", "Unknown")
        unread    = c.get("unreadCount", 0)
        preview   = (c.get("lastMessage") or "")[:120]
        group_tag = " (group)" if c.get("isGroup") else ""
        unread_str = f" [{unread} unread]" if unread else ""
        lines.append(f"{i}. {name}{group_tag}{unread_str}")
        if preview:
            lines.append(f"   Last: {preview}")
        lines.append("")

    return "\n".join(lines).strip()


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
    chats = get_chats()
    return format_chats_for_claude(chats)
