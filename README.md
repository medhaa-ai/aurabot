# AuraBot

Your always-on AI chief-of-staff. Built with Electron + Python (FastAPI) + Claude.

**Capabilities:** Chat with Claude, web search, Gmail, Google Calendar, WhatsApp read, reminders, daily motivation nudges.

**Data stays local** — everything lives in `~/.aurabot/` on your machine.

## Quick start (Windows)

See [SETUP.md](SETUP.md) for the full step-by-step guide.

```powershell
cd C:\Users\medha\AuraBot
npm install
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm start
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | Electron 33 |
| AI backend | Python 3.11 + FastAPI + Uvicorn |
| AI model | Claude (claude-sonnet-4-6) via Anthropic API |
| Memory | ChromaDB with hash-based embeddings |
| Integrations | Gmail API, Google Calendar API, whatsapp-web.js |
| Encryption | Fernet (cryptography) + keyring |

## Project structure

```
electron/     Electron main process + Python spawner
frontend/     HTML/CSS/JS UI
backend/      FastAPI app + all business logic
  memory/     Long-term ChromaDB memory
  nudges/     Scheduler + motivational nudges
  integrations/  Gmail, Calendar, WhatsApp, web search
  platform_adapter/  OS abstraction (Windows / macOS)
whatsapp_bridge/  Node.js bridge (whatsapp-web.js)
scripts/      Build helpers (icon gen, Windows installer)
tests_e2e/    End-to-end smoke tests
```

## Running self-tests

With the app running in one terminal, run in a second terminal:

```powershell
.\venv\Scripts\Activate.ps1
python backend\tests\test_phase8.py
```

## Building the installer

```powershell
.\scripts\build.ps1
```

Outputs `dist\AuraBot Setup 1.0.0.exe`.
