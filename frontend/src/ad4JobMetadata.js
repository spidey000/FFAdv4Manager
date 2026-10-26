// Adventurer 4 job annotations. Only G-code comments are added; never motion,
// heater or tool-changing instructions. FFAD4Manager converts the PNG to GX BMP.
const W = 80
const H = 60

export function formatPrintDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0))
  return `${Math.floor(value / 3600)}h ${Math.floor(value % 3600 / 60)}m ${value % 60}s`
}

function settingNumber(value) {
  const candidate = Array.isArray(value) ? value[0] : value
  if (candidate == null || candidate === '') return null
  const n = Number(candidate)
  return Number.isFinite(n) && n >= 0 ? n : null
}

function hasComment(gcode, name) {
  return new RegExp(`^;\\s*${name}\\s*=`, 'im').test(gcode)
}

function addComment(lines, gcode, key, value) {
  if (value == null || hasComment(gcode, key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))) return
  lines.push(`; ${key} = ${value}`)
}

/** Render the viewer's plate RGBA as a browser-native PNG G-code thumbnail. */
export function thumbnailBlockFromRgba(rgba, canvasFactory = () => document.createElement('canvas')) {
  if (!rgba || rgba.length !== W * H * 4) return ''
  const canvas = canvasFactory()
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext?.('2d')
  if (!ctx) return ''
  const image = ctx.createImageData(W, H)
  // Solid black background is required by the legacy GX preview. Alpha composited
  // here, as well as by the CLI converter, for consistent results.
  for (let i = 0; i < rgba.length; i += 4) {
    const alpha = rgba[i + 3] / 255
    image.data[i] = Math.round(rgba[i] * alpha)
    image.data[i + 1] = Math.round(rgba[i + 1] * alpha)
    image.data[i + 2] = Math.round(rgba[i + 2] * alpha)
    image.data[i + 3] = 255
  }
  ctx.putImageData(image, 0, 0)
  const dataUrl = canvas.toDataURL('image/png')
  if (!dataUrl.startsWith('data:image/png;base64,')) return ''
  const base64 = dataUrl.split(',')[1]
  const rows = base64.match(/.{1,76}/g) || []
  return `; thumbnail begin ${W}x${H} ${base64.length}\n${rows.map(row => '; ' + row).join('\n')}\n; thumbnail end\n`
}

/** Add estimated duration, material usage and available slicer settings to the job. */
export function annotateAd4Gcode(gcode, stats, settings = {}, rgba = null, canvasFactory) {
  const raw = String(gcode || '')
  const comments = []
  const time = settingNumber(stats?.time_estimate ?? stats?.timeSec)
  if (time > 0) addComment(comments, raw, 'estimated printing time (normal mode)', formatPrintDuration(time))
  const filament = settingNumber(stats?.filament_mm ?? stats?.filament)
  if (filament != null) addComment(comments, raw, 'filament used [mm]', filament.toFixed(2))
  const layer = settingNumber(settings.layer_height)
  if (layer > 0) addComment(comments, raw, 'layer_height', layer)
  const shells = settingNumber(settings.wall_loops ?? settings.perimeters)
  if (shells != null) addComment(comments, raw, 'wall_loops', shells)
  const speed = settingNumber(settings.outer_wall_speed ?? settings.perimeter_speed)
  if (speed != null) addComment(comments, raw, 'print_speed', speed)
  const bed = settingNumber(settings.bed_temperature)
  if (bed != null) addComment(comments, raw, 'bed_temperature', bed)
  const nozzle = settingNumber(settings.nozzle_temperature ?? settings.temperature)
  if (nozzle != null) addComment(comments, raw, 'nozzle_temperature', nozzle)
  const density = settingNumber(settings.sparse_infill_density)
  if (density != null) addComment(comments, raw, 'fill_density', density)
  const pattern = settings.sparse_infill_pattern
  if (typeof pattern === 'string' && /^[a-z_0-9-]+$/i.test(pattern)) addComment(comments, raw, 'fill_pattern', pattern)
  let thumbnail = ''
  if (!/^;\s*thumbnail begin\b/im.test(raw)) {
    try { thumbnail = thumbnailBlockFromRgba(rgba, canvasFactory) }
    catch { /* A failed GPU/canvas render must never block sending printable G-code. */ }
  }
  return comments.map(line => line + '\n').join('') + thumbnail + raw
}

/** 0.4.0 viewer exposes the same off-screen plate-thumbnail renderer used by Export.
 * Graceful fallback: this helper returns null if the viewer API is unavailable.
 */
export function captureAd4PlateThumbnail(plate = 0) {
  try {
    return window.__vpApi?.()?.renderThumbnail?.(plate, W, H) ?? null
  } catch {
    return null
  }
}
