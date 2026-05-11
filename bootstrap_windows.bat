@echo off
:: AuraBot Windows bootstrap — runs all setup steps automatically.
:: Run this once after cloning the repo on a fresh Windows machine.

echo.
echo ============================================================
echo  AuraBot Bootstrap — Windows
echo ============================================================
echo.

:: ── Check Node.js ───────────────────────────────────────────────────────────
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Download from https://nodejs.org and re-run.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do echo Node.js: %%v

:: ── Check Python ────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Download from https://www.python.org and re-run.
    echo        Tick "Add Python to PATH" in the installer.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo Python: %%v

:: ── npm install ─────────────────────────────────────────────────────────────
echo.
echo [1/4] Installing Node dependencies...
call npm install
if errorlevel 1 ( echo FAIL: npm install failed. & pause & exit /b 1 )

:: ── Python venv ─────────────────────────────────────────────────────────────
echo.
echo [2/4] Creating Python virtual environment...
if not exist venv (
    python -m venv venv
    if errorlevel 1 ( echo FAIL: venv creation failed. & pause & exit /b 1 )
) else (
    echo        venv already exists, skipping.
)

:: ── pip install ─────────────────────────────────────────────────────────────
echo.
echo [3/4] Installing Python packages (this takes 3-5 minutes)...
call venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 ( echo FAIL: pip install failed. & pause & exit /b 1 )

:: ── WhatsApp bridge deps ────────────────────────────────────────────────────
echo.
echo [4/4] Installing WhatsApp bridge dependencies...
if exist whatsapp_bridge (
    pushd whatsapp_bridge
    call npm install
    popd
) else (
    echo        whatsapp_bridge/ not found, skipping.
)

echo.
echo ============================================================
echo  Setup complete! Run:  npm start
echo ============================================================
echo.
pause
