# AuraBot — Setup Guide (Windows 11)

All commands are for **Windows PowerShell**. Copy-paste them exactly.

---

## Step 1 — Install prerequisites

### Node.js 20 LTS
Download and install from: https://nodejs.org/en/download  
Choose "Windows Installer (.msi)" — the **LTS** version.

After installing, verify:
```powershell
node --version
# Should print: v20.x.x

npm --version
# Should print: 10.x.x
```

### Python 3.11
Download from: https://www.python.org/downloads/release/python-3119/  
Choose "Windows installer (64-bit)".

**Important:** On the first screen of the installer, tick **"Add Python to PATH"** before clicking Install.

After installing, verify:
```powershell
python --version
# Should print: Python 3.11.x
```

---

## Step 2 — Navigate to the project folder

```powershell
cd C:\Users\medha\AuraBot
```

---

## Step 3 — Install Node dependencies

```powershell
npm install
```

This installs Electron and electron-builder. It may take 2-3 minutes.

---

## Step 4 — Create Python virtual environment

```powershell
python -m venv venv
```

Activate it:
```powershell
.\venv\Scripts\Activate.ps1
```

If you get a permissions error, run this first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activating again.

You should see `(venv)` at the start of your prompt.

---

## Step 5 — Install Python dependencies

```powershell
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, Claude API client, ChromaDB, and all other libraries. Takes 3-5 minutes.

---

## Step 6 — Run the app

```powershell
npm start
```

The AuraBot window will appear after ~5 seconds (Python backend starts first).

> **Note for VS Code / Claude Code users:** If you launch the app from inside VS Code's integrated terminal, it works because `npm start` uses `launch.js` which automatically removes the `ELECTRON_RUN_AS_NODE=1` environment variable that VS Code sets. If you launch from a normal Windows Terminal or Command Prompt, there's no issue.
>
> If the window never appears and the error mentions `TypeError: Cannot read properties of undefined (reading 'whenReady')`, open a **Windows Terminal** (not VS Code's terminal) and run `npm start` from there.

---

## Step 7 — Run self-tests

With the app running, open a **second** PowerShell window:

```powershell
cd C:\Users\medha\AuraBot
.\venv\Scripts\Activate.ps1
python backend\tests\test_phase8.py
```

All 11 packaging-readiness tests should pass. Individual phase tests are also available:
`test_phase1.py` through `test_phase8.py` in `backend\tests\`.

If any tests fail, check `%USERPROFILE%\.aurabot\logs\backend.log`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "python is not recognized" | Re-run Python installer, tick "Add to PATH" |
| Window opens but stays on "Starting AuraBot…" | Check `%USERPROFILE%\.aurabot\logs\backend.log` |
| "Activate.ps1 cannot be loaded" | Run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Port 8765 already in use | Kill the process: `netstat -ano \| findstr :8765` then `taskkill /PID <pid> /F` |

---

## Where your data lives

All AuraBot data is stored in `%USERPROFILE%\.aurabot\` (i.e. `C:\Users\medha\.aurabot\`).  
Nothing is ever sent to the internet without your explicit API keys configured.

```
~/.aurabot/
├── settings.json      ← your preferences (not secrets)
├── permissions.json   ← granted permissions
├── window_state.json  ← saved window position/size
├── logs/
│   ├── backend.log    ← Python backend log (check this first when debugging)
│   └── backend.log.*  ← rotated old logs
└── memory/            ← AI memory (Phase 4)
```
