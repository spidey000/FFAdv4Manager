import test from 'node:test'
import assert from 'node:assert/strict'
import { annotateAd4Gcode, thumbnailBlockFromRgba, formatPrintDuration } from '../src/ad4JobMetadata.js'

test('kernel duration, filament, printer settings are emitted as comments without moving G-code', () => {
  const original = 'G28\nM104 S205\nG1 X20 Y10 E1\n'
  const output = annotateAd4Gcode(original,
    { time_estimate: 3723.2, filament_mm: 1345.7 },
    { layer_height: 0.18, wall_loops: 3, outer_wall_speed: 45, bed_temperature: 60, nozzle_temperature: 205 })
  assert.match(output, /; estimated printing time \(normal mode\) = 1h 2m 3s/)
  assert.match(output, /; filament used \[mm\] = 1345\.70/)
  assert.match(output, /; layer_height = 0\.18/)
  assert.match(output, /; wall_loops = 3/)
  assert.match(output, /; print_speed = 45/)
  assert.match(output, /; bed_temperature = 60/)
  assert.match(output, /; nozzle_temperature = 205/)
  assert.ok(output.endsWith(original))
  assert.equal(output.split('G28').length, 2)
})

test('unknown duration and filament are not fabricated', () => {
  const result = annotateAd4Gcode('G1 X1\n', {}, {})
  assert.doesNotMatch(result, /estimated printing time|filament used|nozzle_temperature/)
  assert.equal(formatPrintDuration(3723), '1h 2m 3s')
})

test('existing metadata and PNG are not duplicated', () => {
  const gcode = '; estimated printing time (normal mode) = 0h 4m 2s\n; thumbnail begin 80x60 8\n; ABCDEFGH\n; thumbnail end\nG1 X1\n'
  const out = annotateAd4Gcode(gcode, { time_estimate: 242 }, {})
  assert.equal(out.match(/estimated printing time/g).length, 1)
  assert.equal(out.match(/thumbnail begin/g).length, 1)
})

test('PNG thumbnail encoding uses real RGBA plate pixels, with dark background', () => {
  const pixels = new Uint8Array(80 * 60 * 4)
  pixels.set([240, 80, 40, 255], 0)
  pixels.set([255, 255, 255, 0], 4)
  let result = null
  const fake = () => ({
    width: 0, height: 0,
    getContext: () => ({
      createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
      putImageData: image => { result = image.data },
    }),
    toDataURL: () => 'data:image/png;base64,iVBORw0KGgo=',
  })
  const block = thumbnailBlockFromRgba(pixels, fake)
  assert.match(block, /thumbnail begin 80x60 12/)
  assert.match(block, /; iVBORw0KGgo=/)
  assert.deepEqual(Array.from(result.slice(0, 8)), [240, 80, 40, 255, 0, 0, 0, 255])
})
