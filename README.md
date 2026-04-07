# VARA Term

VARA BBS Terminal Client with HMAC-SHA256 authentication, rig control, and macro support.

A PyQt6 desktop application for connecting to amateur radio BBS systems over VARA FM and VARA HF modems.

## Features

- Connect to VARA BBS stations over FM and HF
- Automatic HMAC-SHA256 authentication
- OmniRig PTT control for HF
- Hamlib and FLrig rig control support
- Connection profiles and target history
- Configurable macro buttons
- Real-time S/N graph
- Session logging
- Dark theme terminal display

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python src/main.py` (or double-click `start_vterm.bat`)
3. Configure your callsign in Settings > Terminal Setup
4. Enter the target BBS callsign and click Connect

## Contributors

- **KK4ODA** (Facundo) — Author
- **Claude** (Anthropic) — Co-developer
