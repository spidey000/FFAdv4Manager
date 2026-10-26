# Integration and functionality overview

ThreeSlicer Responsive is a React integration of **`three-slicer@0.4.0`** and **`three-slicer-viewer@0.4.0`**, configured for the bundled Adventurer 4 0.4 mm printer profile. It is not the original illustrative HTML mockup.

## Connected application modules

| Component | Integration | Result |
| --- | --- | --- |
| 3D viewport and scene | `<Viewport />` from `three-slicer-viewer` | Model loading, editing, transformations, plates, paint tools, preview and exports as provided by upstream. |
| Slicing worker | `useSlicer` + `makeSlicerWorker` | Browser-based WebAssembly slicing. |
| Printer preset | `bundledCatalog`, `printerSettings(AD4)` | Fixed Adventurer 4 Series 0.4 Nozzle profile. |
| Process/filament catalog | `processPresets()` and `filamentPresets()` | Recommended presets and adjustable shared settings. |
| Advanced settings | `SettingsPanel`, `schema`, `uiTree`, `makeCfg`, `disabledKeys` | Schema-driven option controls and dependency rules. |
| Mobile Slice / Auto slice | `sliceRequest` / React state | Real slicer requests and invalidation on edits. |
| Layer and nozzle playback | `src/previewBridge.js` | Drives the original upstream preview controls. |
| Printer integration | `server/ad4_bridge.py` and FFAD4Manager | Status, camera snapshots, file listing/printing, discovery, job controls, diagnostics, fan on/off, bounded timelapse, Linux notifications, connection profiles and uploads on the local host. |

The slicer, viewer and editable settings share one React settings map; the mobile drawer does not maintain a disconnected copy. The responsive rules are injected into open Shadow DOM roots. Desktop retains the upstream sidebar, while smaller screens use a bottom drawer and compact controls.

## Supported vs unsupported functionality

The web UI includes a new Printer Manager, opened from the AD4 status pill. It wires discovered printers, stored remote-file listing/printing, job controls, camera stills, CLI diagnostics, bounded interval timelapse, part-fan on/off, Linux host notifications and named CLI connection profiles. It does **not** provide live camera streaming, push notifications to the phone, an auxiliary fan speed slider, remote deletion/rename, or slicer quality presets via CLI. See [the exact CLI-backed feature contract](PRINTER_MANAGER.md). See the complete [command-by-command matrix](../README.md#what-ffad4manager-can-do--and-what-this-web-ui-exposes).

GitHub Pages serves browser-only slicing. There is no printer-control backend on Pages. The WebGL viewer needs a compatible browser and may use the slicer's single-threaded worker when cross-origin isolation is unavailable. Hardware command responses do not establish print completion or uploaded byte integrity.

## Validation

CI executes a Vite production build and deploys the static site from `main`. A Chromium post-deployment smoke check opens the live URL at several mobile widths and asserts the empty-state panel stays within the viewport. Such tests **do not** validate physical printing. Local printer testing requires deliberate user-supervised verification on the device.
