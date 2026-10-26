# Server (Python API bridge)

`ad4_bridge.py` serves the built `../frontend/dist/` and accepts only named `/api/printer/*` operations, translating them to the real `ffadv4manager` executable. `cloudflare_access.py` checks Cloudflare Access JWT signature, issuer, AUD, expiry and authorized email for remote requests. Run with `ffadv4manager slicer --require-access` in protected production; read [../docs/DEPLOY_CLOUDFLARE.md](../docs/DEPLOY_CLOUDFLARE.md). Never publish unprotected loopback-only mode.
