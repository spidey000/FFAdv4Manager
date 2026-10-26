# CLI (Python printer control)

This is the independently installable Python `ffadv4manager` / `ad4ctl` CLI, incorporating FlashForge TCP communication, status, camera, upload/GX conversion, files, diagnostics, profiles, printing and pause/resume/cancel. `pip install -e .` from repository root installs it. CLI commands work without the web frontend. See [../docs/CLI.md](../docs/CLI.md); the integrated `ffadv4manager slicer` launcher starts `../server/ad4_bridge.py` after the Vite frontend is built.
