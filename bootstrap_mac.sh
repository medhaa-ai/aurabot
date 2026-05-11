#!/usr/bin/env bash
# AuraBot macOS bootstrap — runs all setup steps automatically.
# Run once after cloning: chmod +x bootstrap_mac.sh && ./bootstrap_mac.sh

set -euo pipefail

echo ""
echo "============================================================"
echo " AuraBot Bootstrap — macOS"
echo "============================================================"
echo ""

# ── Check Node.js ─────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found."
    echo "       Install via brew: brew install node@20"
    echo "       Or download from: https://nodejs.org"
    exit 1
fi
echo "Node.js: $(node --version)"

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python not found."
    echo "       Install via brew: brew install python@3.11"
    exit 1
fi
echo "Python:  $($PYTHON --version)"

# ── npm install ───────────────────────────────────────────────────────────────
echo ""
echo "[1/4] Installing Node dependencies..."
npm install

# ── Python venv ───────────────────────────────────────────────────────────────
echo ""
echo "[2/4] Creating Python virtual environment..."
if [ ! -d venv ]; then
    "$PYTHON" -m venv venv
else
    echo "       venv already exists, skipping."
fi

# ── pip install ───────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing Python packages (this takes 3-5 minutes)..."
venv/bin/pip install -r requirements.txt

# ── WhatsApp bridge deps ──────────────────────────────────────────────────────
echo ""
echo "[4/4] Installing WhatsApp bridge dependencies..."
if [ -d whatsapp_bridge ]; then
    (cd whatsapp_bridge && npm install)
else
    echo "       whatsapp_bridge/ not found, skipping."
fi

echo ""
echo "============================================================"
echo " Setup complete! Run:  npm start"
echo "============================================================"
echo ""
