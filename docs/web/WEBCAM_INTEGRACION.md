# Adventurer 4 camera integration

**Current implementation:** the mobile/desktop camera button opens an actual modal. On a local server, `GET /api/printer/camera` calls `ffadv4manager camera snapshot TEMP.jpg` and returns one JPEG image. The modal can request a fresh still using **Refresh snapshot**.

This is not a continuous video player and does not stream the printer's MJPEG feed. If the request fails (including on GitHub Pages, which has no backend), the interface shows a clearly labeled simulated image. It must not be mistaken for the printer's real state.

## Local flow

1. The browser invokes the same-origin local API without directly embedding printer IP addresses.
2. `server/ad4_bridge.py` runs the installed CLI with a temporary filename and a bounded subprocess timeout.
3. FFAD4Manager requests the first complete frame from the printer's MJPEG endpoint (default HTTP `http://PRINTER_IP:8080/?action=stream`) and writes a JPEG file.
4. The local bridge returns JPEG bytes. The browser creates an object URL, displays it, and revokes old object URLs during refresh/cleanup.

The request does not open the printer TCP command connection. Troubleshoot with:

```bash
ffadv4manager camera url
ffadv4manager camera snapshot /tmp/ad4-camera.jpg
```

## Not included

- Continuous MJPEG playback in the ThreeSlicer UI.
- Layer-synchronized timelapse controls. The CLI offers a separate `camera timelapse` command, but the UI does not expose it.
- Authentication or encryption on the printer's camera stream. The local bridge is loopback-only; never publish the unauthenticated stream or bridge to the Internet.

More details: [Local setup](AD4_LOCAL.md) and [CLI integration matrix](../README.md#what-ffad4manager-can-do--and-what-this-web-ui-exposes).
