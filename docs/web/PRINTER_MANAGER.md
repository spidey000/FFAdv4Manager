# Printer Manager (mobile and desktop)

> **Worldwide remote access:** Printer Manager can operate through the self-hosted ThreeSlicer origin protected by Cloudflare Tunnel + Access. Configure **all four** required `CF_ACCESS_*` settings to enable signed origin JWT validation, and follow the [secure deployment instructions](REMOTE_ACCESS.md) before publishing a Tunnel route. The default configuration remains local-only; GitHub Pages is only a slicer demo.

Open the **AD4 / printer-status button** in the top right of ThreeSlicer to access the management screen. The panel reuses the project's lime accent (#a3e635), slate surfaces and existing responsive styles. The existing camera button still opens a single snapshot.

## Actual functionality

This screen calls FFAD4Manager through the **local** Python bridge:

| Screen card | CLI commands | Notes |
| --- | --- | --- |
| Printer state and print progress | status --json | Reads actual telemetry, no demo values. Missing fields show “—”. |
| Current job | pause, resume, cancel | Enables actions based on observed print state; cancelling requires confirmation. |
| Discover/connect | discover --json, then --host | A new host must have been discovered with command port 8899. |
| Stored files | files --json, print REMOTE_NAME | Displays paths only; does not invent size/date/material or unsupported remote deletion. |
| Camera | camera snapshot | Single JPEG on demand, **not** a live stream. |
| Cooling | fan on, fan off | Part cooling only; no numerical fan speed control or enclosure fan control. |
| Diagnostics | doctor, info --json, position --json | Real CLI output; no made-up sensor/system health indicators. |
| Timelapse | camera timelapse FOLDER --interval 10 --count 20 | Fixed, bounded local capture with start/stop. Frames remain on the machine running the bridge. Not layer-synchronized. |
| Notifications | notify --events paused,offline,printing,ready | Starts/stops the **host Linux desktop** notifier (notify-send). Not browser/phone push notifications. |
| Connection profiles | profiles list/add/delete, --profile | CLI printer **connection** profiles, **not** slicer speed/quality presets. |
| Upload | upload FILE or upload FILE --start | Uploads selected G-code/GX up to 100 MiB; starting requires confirmation. |

The original slicer functions, including its existing sliced-G-code upload/print buttons, remain unchanged.

## Running locally

Install FFAD4Manager and build this repository per [AD4_LOCAL.md](AD4_LOCAL.md). Run npm ci, npm run build and npm run local.

Open **http://127.0.0.1:8765/Three_slicer_responsive/** *on the bridge computer*. For development, npm run dev proxies API calls to the local bridge.

**GitHub Pages is a static website.** Its new manager UI is available but its cards correctly show the bridge as unavailable; it does not send commands to your printer. The Python bridge deliberately listens only on **127.0.0.1** without authentication. To use printer controls from a **phone**, an authenticated, encrypted, trusted remote-access setup is needed before making the bridge reachable from the phone. **Never forward port 8765 or 8899 on your router or expose them unauthenticated.**

## Caveats

- Printer firmware/CLI replies do not independently prove a motor/fan's physical effect.
- The existing CLI upload-only path omits M23/M24, but firmware behavior of M601 S1 is insufficiently documented to guarantee no physical start. Supervise the machine.
- A successful upload confirms only printer-side file *name* presence, not byte integrity.
- Timelapse output is stored in the bridge's temporary directory and cleaned on server shutdown/new capture. No gallery, cloud sync or video encoding is provided.
- A Linux desktop session with working notify-send is required for notifications. Alerts are displayed on the bridge computer, not on the phone.
- No auxiliary/enclosure fan slider, remote rename/delete, Home-axes button, material metadata, estimated remaining time, or fabricated live camera feed is shown. These capabilities are not provided by this CLI contract.

Run python3 -m unittest discover -s tests -p 'test_printer_manager_bridge.py' to test the bridge with no actual printer. Hardware-dependent controls require supervised testing on your Adventurer 4.
