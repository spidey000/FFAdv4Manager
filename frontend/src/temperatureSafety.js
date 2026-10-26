// Inspect effective G-code before shipping a job when Artillery PLA Basic is
// selected. FFAD4Manager wraps G-code as GX without rewriting heater commands.
// This guard is not a substitute for supervising the printer.
import { ARTILLERY_PLA_BASIC } from './profileLibrary.js'

const LIMITS = Object.freeze({ nozzle: 220, bed: 65 })
const NOZZLE_METADATA = new Set(['nozzle_temperature', 'first_layer_temperature'])
const BED_METADATA = new Set(['first_layer_bed_temperature', 'bed_temperature'])

function numbers(value) {
  return String(value).split(',').map(part => Number(part.trim())).filter(Number.isFinite)
}

export function checkArtilleryHeating(gcode, selectedMaterial) {
  if (selectedMaterial !== ARTILLERY_PLA_BASIC || typeof gcode !== 'string') return []
  const warnings = new Set()
  for (const line of gcode.split(/\r?\n/)) {
    const comment = line.match(/^\s*;\s*([a-z_]+)\s*=\s*([^\r\n]+)/i)
    if (comment) {
      const key = comment[1].toLowerCase()
      const kind = NOZZLE_METADATA.has(key) ? 'nozzle' : BED_METADATA.has(key) ? 'bed' : null
      if (kind && numbers(comment[2]).some(value => value > LIMITS[kind])) {
        warnings.add(kind + ': metadata exceeds ' + LIMITS[kind] + '°C')
      }
      continue
    }
    const command = line.split(';')[0].trim().toUpperCase()
    const match = command.match(/^(?:N\d+\s+)?(M104|M109|M140|M190)\b/)
    if (!match) continue
    const kind = (match[1] === 'M104' || match[1] === 'M109') ? 'nozzle' : 'bed'
    for (const token of command.matchAll(/\b[SR]\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\b/g)) {
      const value = Number(token[1])
      if (value > LIMITS[kind]) {
        warnings.add(kind + ': ' + match[1] + ' requests ' + value + '°C (PLA max ' + LIMITS[kind] + '°C)')
      }
    }
  }
  return [...warnings]
}
