# Architecture: clear components, one end-to-end workflow

```text
Browser / smartphone (remote or local)
    │  HTTPS (remote only), Cloudflare Access session
    ▼
Cloudflare Tunnel (remote only) -> 127.0.0.1:8765
    ▼
server/ad4_bridge.py
    ├── GET / -> frontend/dist/ (built React/Vite)
    ├── GET /api/printer/status  -> CLI status --json
    ├── GET /api/printer/camera  -> CLI camera snapshot
    ├── GET /api/printer/files   -> CLI files --json
    ├── POST /api/printer/jobs   -> CLI upload / upload --start
    └── other allowlisted /api/printer/* -> CLI commands
    │
    ▼
ffadv4manager/cli.py -> ffadv4manager/core/
    │                     TCP 8899 / camera HTTP 8080 (LAN only)
    ▼
FlashForge Adventurer 4
```

## Boundaries

- **Frontend**: browser-side 3D model editing, WebAssembly slicing, profile state and toolpath review; API calls use same-origin `/api/printer/*`. It has no raw TCP access and is not the authority for printer state.
- **Bridge**: authenticates Access JWT for the configured hostname, validates Host/Origin, allows specific command shapes, constrains filenames, enforces upload size, and invokes the local CLI through `subprocess` with argument arrays (no shell). The bridge listens **only** on `127.0.0.1`.
- **CLI**: printer connection, networking/protocol, camera, upload/print controls, GX conversion and diagnostics. Runnable even when neither React nor the server is running.
- **Printer**: only the CLI-host computer needs LAN access to port 8899 and the printer's configured camera endpoint.

## Actual print flow

1. User opens the protected frontend (static assets served by the bridge).
2. Browser imports a model; slicer produces G-code and preview.
3. User chooses **Upload only** or **Print**, after reviewing the current material and profile.
4. Frontend `POST /api/printer/jobs?start=false|true` sends G-code to the bridge.
5. Bridge writes a bounded temporary file and calls `ffadv4manager upload` (optional `--start`).
6. CLI packages G-code/GX as supported, uploads via the FlashForge protocol and checks the printer's reported listing. Only `--start` requests explicit start.
7. UI reports the CLI result; polling reads the actual printer's status. This is not proof of physical print success or uploaded byte integrity.

## Deployment mode caveats

- The Vite dev server uses port 5173, API proxying to 8765 and is for localhost development.
- The built UI is available directly at `/` on the integrated backend; no GitHub Pages base path is used.
- In local mode the bridge has loopback Host/Origin checks but **no remote user authentication**. Do not tunnel it.
- In remote mode the bridge requires signed Cloudflare Access assertions and the exact allowed email, with Access at the edge as the first enforcement point.
- Historical `ffadv4manager/slicer_bridge.py` is retained for upstream CLI compatibility tests/reference but the `ffadv4manager slicer` entrypoint uses `server/ad4_bridge.py` in this monorepo.
