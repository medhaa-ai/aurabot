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

## Quick start (macOS)

No manual installs needed — the bootstrap script handles **Homebrew, Node.js, Python, and all packages** automatically.

Open **Terminal** and paste these two lines:

```bash
git clone https://github.com/medhaa-ai/aurabot.git
cd aurabot && chmod +x bootstrap_mac.sh && ./bootstrap_mac.sh
```

> First run takes ~5 minutes while Python packages download. You'll be prompted for your password once (for Homebrew).

Then launch:

```bash
npm start
```

AuraBot opens as a floating window. You'll be prompted for your [Anthropic API key](https://console.anthropic.com) on first launch — it's free to get started.

### Install as a proper macOS app (optional)

If you want AuraBot to live in your Applications folder and launch from the Dock like any other app, follow these steps — all done in **Terminal** inside the `aurabot` folder:

**Step 1** — still in Terminal, run:
```bash
npm run package:mac
```
This takes ~2 minutes and creates a file at `dist/AuraBot-1.0.0.dmg` inside the aurabot folder.

**Step 2** — open the `.dmg`:
```bash
open dist/AuraBot-1.0.0.dmg
```
A Finder window pops up showing the AuraBot icon and an Applications shortcut.

**Step 3** — drag the **AuraBot** icon into the **Applications** folder shown in that window.

**Step 4** — eject the disk image (drag it to Trash or press Cmd+E), then open **Launchpad** or **Applications** and double-click **AuraBot**. It'll appear in your Dock from now on.

> You only need to do this once. After that, launch AuraBot directly from the Dock — no Terminal needed.

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
