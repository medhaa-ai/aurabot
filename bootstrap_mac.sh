#!/usr/bin/env bash
# AuraBot macOS bootstrap — installs all prerequisites and sets up the app.
# Run once after cloning:
#   chmod +x bootstrap_mac.sh && ./bootstrap_mac.sh

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BOLD}============================================================"
echo " AuraBot Setup — macOS"
echo -e "============================================================${NC}"
echo ""

# ── 1. Homebrew ────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo -e "${YELLOW}[1/6] Installing Homebrew (requires your password)...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
    fi
    echo -e "${GREEN}  Homebrew installed.${NC}"
else
    echo -e "${GREEN}[1/6] Homebrew already installed — skipping.${NC}"
fi

# ── 2. Node.js ─────────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo -e "${YELLOW}[2/6] Installing Node.js 20...${NC}"
    brew install node@20
    brew link --overwrite node@20
    echo -e "${GREEN}  Node.js $(node --version) installed.${NC}"
else
    echo -e "${GREEN}[2/6] Node.js $(node --version) already installed — skipping.${NC}"
fi

# ── 3. Python ──────────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.11 python3.12 python3.13 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${YELLOW}[3/6] Installing Python 3.11...${NC}"
    brew install python@3.11
    PYTHON="python3.11"
    echo -e "${GREEN}  Python $($PYTHON --version) installed.${NC}"
else
    echo -e "${GREEN}[3/6] Python $($PYTHON --version) already installed — skipping.${NC}"
fi

# ── 4. Node dependencies ───────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/6] Installing Node dependencies...${NC}"
npm install
echo -e "${GREEN}  Done.${NC}"

# ── 5. Python virtual environment + packages ───────────────────────────────────
echo ""
echo -e "${YELLOW}[5/6] Setting up Python environment (takes 3-5 min first time)...${NC}"
if [ ! -d venv ]; then
    "$PYTHON" -m venv venv
fi
venv/bin/pip install --upgrade pip --quiet
venv/bin/pip install -r requirements.txt --quiet
echo -e "${GREEN}  Python packages installed.${NC}"

# ── 6. WhatsApp bridge ─────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[6/6] Installing WhatsApp bridge dependencies...${NC}"
if [ -d whatsapp_bridge ]; then
    (cd whatsapp_bridge && npm install --silent)
    echo -e "${GREEN}  Done.${NC}"
else
    echo "  whatsapp_bridge/ not found — skipping."
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}============================================================"
echo " Setup complete!"
echo -e "============================================================${NC}"
echo ""
echo -e "  Start AuraBot:          ${BOLD}npm start${NC}"
echo -e "  Build a .dmg installer: ${BOLD}npm run package:mac${NC}"
echo ""
echo -e "${YELLOW}  First launch will ask for your Anthropic API key.${NC}"
echo -e "${YELLOW}  Get one free at: https://console.anthropic.com${NC}"
echo ""
