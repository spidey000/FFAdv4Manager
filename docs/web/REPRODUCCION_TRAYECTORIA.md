# Toolpath exploration and playback

After slicing a filament model, the upstream Three Slicer viewer can render toolpaths, travels, layers and a simulated nozzle position. The bottom panel interacts with the **same actual upstream preview**, not a second or illustrative animation.

## Controls

| UI control | Behavior |
| --- | --- |
| **Layers** | Select the last visible layer (the previous layers remain visible by default). |
| **Single layer** | Isolate the selected layer. |
| **Movement** | Move through toolpath moves within the selected layer and update the nozzle marker. |
| **Play** | Animate the planned toolpath at a simulated 80 moves/s. |
| **Fast-forward ×8** | Simulated fast playback at eight times the base move rate. |
| **Pause** | Stop the animation at the current position. |
| **Stop** | Reset the timeline to the beginning. |
| **Expand/collapse** | Show advanced controls or conserve workspace space on mobile. |

This is a **move-count visualization**, **not** a print-time predictor or control command. It does not model real printer acceleration, heaters, wait commands or external firmware behavior, and it does not contact the printer. FFF has nozzle moves; resin output is layer-based.

## Implementation

`three-slicer-viewer@0.4.0` emits events for layer/move changes but does not offer controlled inputs for all movements through its public React props. The local `src/previewBridge.js` adapter accesses the upstream Preview range elements in the open Shadow DOM, writes values using the native input setter and dispatches input/change events. This retains ownership of the actual toolpath geometry and nozzle marker in the original viewer.

Playback uses `requestAnimationFrame`; it pauses on manual scrubbing, plate changes, re-slicing or leaving Preview. The UI limits text-label update frequency and reserves enough bottom space to avoid overlapping controls. If the upstream viewer package is updated, verify the selectors (`layer-hi`, `layer-lo`, `move-range`, `single-layer-btn`, `move-reset`) and replace the adapter with a public API if the library introduces one.
