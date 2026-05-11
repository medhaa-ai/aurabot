# Moving AuraBot to macOS

## What transfers automatically

Your AI memory, settings, and API keys are stored in `~/.aurabot/` on each machine separately. They do **not** sync between machines — you'll re-enter your API keys on the Mac.

## Prerequisites on Mac

Install these before running AuraBot:

```bash
# Node.js 20 LTS — download from https://nodejs.org or via brew:
brew install node@20

# Python 3.11
brew install python@3.11
```

## Setup on Mac

```bash
cd ~/AuraBot          # or wherever you copied the project
npm install
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm start
```

## WhatsApp bridge on Mac

The `whatsapp_bridge/` directory must have its own `node_modules`:

```bash
cd whatsapp_bridge
npm install
cd ..
```

## Building a macOS .dmg

```bash
npm run package:mac
```

Outputs `dist/AuraBot-1.0.0.dmg`. Requires Xcode command-line tools.

## Transferring your data

If you want to copy existing memory and settings from Windows:

1. On Windows, export memory from **Settings → Memory → Export JSON** and save the file.
2. On Mac, import via the same Settings panel after setup.

API keys must be re-entered manually on the new machine — they are machine-bound by design.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python3.11: command not found` | Use `python3` or add brew Python to PATH |
| Electron window doesn't open | Run `npm start` from Terminal (not VS Code) |
| WhatsApp QR never appears | Run `cd whatsapp_bridge && npm install` |
