import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PROFILE_STORAGE_KEY, ARTILLERY_PLA_BASIC,
  emptyProfileLibrary, snapshotPreset, readProfileLibrary, writeProfileLibrary,
  addCustomProfile, replaceCustomProfile, removeCustomProfile, makeArtilleryPlaBasic,
} from '../src/profileLibrary.js'
import { AD4_SAFE_PROCESS_OVERRIDES, applyAd4SafeProcess } from '../src/ad4SafeProfile.js'

const makeStorage = () => {
  const map = new Map()
  return {
    getItem: key => map.get(key) ?? null,
    setItem: (key, value) => map.set(key, value),
    raw: key => map.get(key),
  }
}
const num = v => {
  const value = Array.isArray(v) ? v[0] : v
  return typeof value === 'string' && value.trim().endsWith('%') ? Number(value.trim().slice(0, -1)) : Number(value)
}

test('all bundled AD4 process profiles inherit the same conservative motion settings', () => {
  const presets = [
    { layer_height: 0.13, outer_wall_speed: [80], default_acceleration: [5000] },
    { layer_height: 0.20, outer_wall_speed: [50], default_acceleration: [5000] },
    { layer_height: 0.30, outer_wall_speed: [50], default_acceleration: [8000] },
  ].map(applyAd4SafeProcess)
  for (const key of Object.keys(AD4_SAFE_PROCESS_OVERRIDES)) {
    assert.ok(presets.every(item => JSON.stringify(item[key]) === JSON.stringify(AD4_SAFE_PROCESS_OVERRIDES[key])), key)
  }
  assert.deepEqual(presets.map(p => p.layer_height), [0.13, 0.20, 0.30])
})

test('custom process profiles capture only process keys, never material or printer values', () => {
  const processKeys = ['outer_wall_speed', 'layer_height', 'default_acceleration']
  const settings = { outer_wall_speed: [29], layer_height: 0.2, default_acceleration: [450],
    nozzle_temperature: [210], machine_max_speed_x: [90] }
  const next = addCustomProfile(emptyProfileLibrary(), 'process', '  Fine   detail  ', settings, processKeys,
    ['0.20mm Standard @Flashforge AD4 0.4 Nozzle'])
  assert.equal(next.process[0].name, 'Fine detail')
  assert.deepEqual(next.process[0].values, {
    outer_wall_speed: [29], layer_height: 0.2, default_acceleration: [450],
  })
  settings.outer_wall_speed[0] = 100
  assert.equal(next.process[0].values.outer_wall_speed[0], 29)
  assert.equal(next.filament.length, 0)
  assert.deepEqual(snapshotPreset({}, processKeys), {})
})

test('custom filament profiles preserve modified temperature, flow and cooling separately', () => {
  const process = addCustomProfile(emptyProfileLibrary(), 'process', 'Precise',
    { outer_wall_speed: [35] }, ['outer_wall_speed'])
  const material = addCustomProfile(process, 'filament', 'Artillery personalized',
    { nozzle_temperature: [207], filament_flow_ratio: [0.97], fan_max_speed: [85], outer_wall_speed: [35] },
    ['nozzle_temperature', 'filament_flow_ratio', 'fan_max_speed'], [ARTILLERY_PLA_BASIC])
  assert.deepEqual(material.filament[0].values, {
    nozzle_temperature: [207], filament_flow_ratio: [0.97], fan_max_speed: [85],
  })
  assert.deepEqual(material.process[0].values, { outer_wall_speed: [35] })
})

test('profiles survive a page reload and can be updated or deleted without changing the other type', () => {
  const storage = makeStorage()
  let library = emptyProfileLibrary()
  library = addCustomProfile(library, 'process', 'My safe process', { outer_wall_speed: [34] }, ['outer_wall_speed'])
  library = addCustomProfile(library, 'filament', 'My PLA', { nozzle_temperature: [205] }, ['nozzle_temperature'])
  writeProfileLibrary(storage, library)
  assert.equal(JSON.parse(storage.raw(PROFILE_STORAGE_KEY)).version, 1)
  let restored = readProfileLibrary(storage)
  assert.equal(restored.process[0].name, 'My safe process')
  restored = replaceCustomProfile(restored, 'filament', 'My PLA', { nozzle_temperature: [215] }, ['nozzle_temperature'])
  writeProfileLibrary(storage, restored)
  assert.equal(readProfileLibrary(storage).filament[0].values.nozzle_temperature[0], 215)
  assert.equal(readProfileLibrary(storage).process[0].values.outer_wall_speed[0], 34)
  restored = removeCustomProfile(restored, 'process', 'My safe process')
  assert.equal(restored.process.length, 0)
  assert.equal(restored.filament.length, 1)
})

test('names are validated and duplicate upstream or local names are rejected', () => {
  const lib = addCustomProfile(emptyProfileLibrary(), 'process', 'My Custom', { layer_height: .2 }, ['layer_height'])
  assert.throws(() => addCustomProfile(lib, 'process', 'my custom', { layer_height: .3 }, ['layer_height']), /already used/)
  assert.throws(() => addCustomProfile(lib, 'process', 'Standard', { layer_height: .3 }, ['layer_height'], ['Standard']), /already used/)
  assert.throws(() => addCustomProfile(lib, 'process', '<bad>', { layer_height: .3 }, ['layer_height']), /profile name/)
  assert.throws(() => addCustomProfile(lib, 'filament', 'X', { filament_type: ['PLA'] }, ['filament_type']), /profile name/)
})

test('storage failures are surfaced instead of claiming the profile was saved', () => {
  const inaccessible = { getItem: () => { throw Error('blocked') }, setItem: () => { throw Error('blocked') } }
  assert.deepEqual(readProfileLibrary(inaccessible), emptyProfileLibrary())
  assert.throws(() => writeProfileLibrary(inaccessible, emptyProfileLibrary()), /blocked/)
})

test('Artillery PLA Basic retains AD4 PLA compatibility and uses cautious non-HS settings', () => {
  const stock = {
    filament_vendor: ['Generic'], filament_type: ['PLA'], filament_flow_ratio: [1.07],
    enable_pressure_advance: true, pressure_advance: [0.8],
    nozzle_temperature: [210], retraction_length: [5],
  }
  const result = makeArtilleryPlaBasic(stock)
  assert.equal(result.filament_vendor[0], 'Artillery')
  assert.equal(result.filament_type[0], 'PLA')
  assert.equal(num(result.nozzle_temperature), 205)
  assert.equal(num(result.nozzle_temperature_initial_layer), 210)
  assert.equal(num(result.nozzle_temperature_range_low), 190)
  assert.equal(num(result.nozzle_temperature_range_high), 220)
  assert.equal(num(result.hot_plate_temp), 55)
  assert.equal(num(result.filament_max_volumetric_speed), 10)
  assert.equal(result.enable_pressure_advance, false)
  assert.equal(num(result.pressure_advance), 0)
  assert.deepEqual(result.retraction_length, [5])
  assert.deepEqual(stock.filament_vendor, ['Generic'])
})
