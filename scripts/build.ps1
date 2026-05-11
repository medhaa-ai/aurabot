# AuraBot Windows build script
# Run from the AuraBot root: .\scripts\build.ps1
#
# Prerequisites:
#   - Node.js 18+ (https://nodejs.org)
#   - Python 3.10+  (https://python.org)
#   - Pillow        (pip install pillow)

param(
    [switch]$SkipIcons,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host ""
Write-Host "=== AuraBot Windows Build ===" -ForegroundColor Cyan
Write-Host ""

# ── Prerequisites check ────────────────────────────────────────────────────
Write-Host "[0/4] Checking prerequisites..."

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js not found. Install from https://nodejs.org and re-run."
    exit 1
}
$nodeVer = node --version
Write-Host "  node $nodeVer"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install from https://python.org and re-run."
    exit 1
}
$pyVer = python --version
Write-Host "  $pyVer"

# ── Icons ──────────────────────────────────────────────────────────────────
if (-not $SkipIcons) {
    Write-Host ""
    Write-Host "[1/4] Generating app icons..."
    python scripts\make_icons.py
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "  Icon generation failed. Install Pillow: pip install pillow"
        Write-Warning "  Continuing without updated icons (existing icons will be used)."
    }
    else {
        Write-Host "  Icons generated." -ForegroundColor Green
    }
}
else {
    Write-Host "[1/4] Skipping icon generation (--SkipIcons)."
}

# ── npm install ────────────────────────────────────────────────────────────
if (-not $SkipInstall) {
    Write-Host ""
    Write-Host "[2/4] Installing npm dependencies..."
    npm install --prefer-offline 2>&1 | Where-Object { $_ -notmatch "^npm warn" }
    if ($LASTEXITCODE -ne 0) { Write-Error "npm install failed."; exit 1 }
    Write-Host "  npm dependencies ready." -ForegroundColor Green
}
else {
    Write-Host "[2/4] Skipping npm install (--SkipInstall)."
}

# ── Ensure icon.ico exists ─────────────────────────────────────────────────
if (-not (Test-Path "frontend\icons\icon.ico")) {
    Write-Error "frontend\icons\icon.ico not found. Run without --SkipIcons or add the file manually."
    exit 1
}

# ── electron-builder ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Building Windows installer (this takes a few minutes)..."
npx electron-builder --win 2>&1
if ($LASTEXITCODE -ne 0) { Write-Error "electron-builder failed."; exit 1 }

# ── Done ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Build complete!" -ForegroundColor Green

$installer = Get-ChildItem -Path "dist" -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($installer) {
    $sizeMB = [math]::Round($installer.Length / 1MB, 1)
    Write-Host ""
    Write-Host "  Installer : $($installer.FullName)" -ForegroundColor Cyan
    Write-Host "  Size      : $sizeMB MB" -ForegroundColor Cyan
}
else {
    Write-Host "  Installer created in dist\" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "First-time install note:" -ForegroundColor Yellow
Write-Host "  The app creates a Python venv at ~/.aurabot/venv/ on first launch."
Write-Host "  This takes 2-3 minutes and requires Python 3.10+ to be installed."
