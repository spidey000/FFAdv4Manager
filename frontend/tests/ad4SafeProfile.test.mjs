import test from 'node:test'
import assert from 'node:assert/strict'
import {
  AD4_STOCK_PROCESS, AD4_SAFE_PROCESS, AD4_SAFE_MACHINE_LIMITS, AD4_SAFE_PROCESS_OVERRIDES,
  applyAd4SafeMachineLimits, applyAd4SafeProcess,
} from '../src/ad4SafeProfile.js'

const value = v => Number(Array.isArray(v) ? v[0] : v)

test('the conservative profile is distinct from the unmodified Orca standard profile', () => {
  assert.notEqual(AD4_SAFE_PROCESS, AD4_STOCK_PROCESS)
  const stock = { outer_wall_speed: [50], sparse_infill_speed: [60], bridge_speed: [25], layer_height: 0.2 }
  const result = applyAd4SafeProcess(stock)
  assert.equal(value(result.outer_wall_speed), 35)
  assert.equal(value(result.bridge_speed), 25)
  assert.equal(result.layer_height, 0.2)
  assert.deepEqual(stock.outer_wall_speed, [50], 'Orca source process must not be mutated')
  assert.throws(() => applyAd4SafeProcess(null), /Missing OrcaSlicer/)
})

test('all conservative extrusion roles are at most 60 mm/s', () => {
  const extrusionKeys = [
    'initial_layer_speed', 'initial_layer_infill_speed', 'outer_wall_speed', 'inner_wall_speed',
    'sparse_infill_speed', 'internal_solid_infill_speed', 'top_surface_speed', 'gap_infill_speed',
    'support_speed', 'support_interface_speed',
  ]
  for (const key of extrusionKeys) {
    assert.ok(value(AD4_SAFE_PROCESS_OVERRIDES[key]) > 0, key)
    assert.ok(value(AD4_SAFE_PROCESS_OVERRIDES[key]) <= 60, key)
  }
  assert.ok(value(AD4_SAFE_PROCESS_OVERRIDES.travel_speed) <= 80)
  assert.ok(value(AD4_SAFE_PROCESS_OVERRIDES.initial_layer_travel_speed) <= 80)
})

test('process accelerations stay below conservative machine ceilings', () => {
  const ceiling = value(AD4_SAFE_MACHINE_LIMITS.machine_max_acceleration_extruding)
  for (const [key, setting] of Object.entries(AD4_SAFE_PROCESS_OVERRIDES)) {
    if (key.includes('acceleration')) {
      assert.ok(value(setting) <= ceiling, key)
      assert.ok(value(setting) > 0, key)
    }
  }
  const machine = { machine_max_speed_x: [100], nozzle_diameter: [0.4] }
  const result = applyAd4SafeMachineLimits(machine)
  assert.equal(value(result.machine_max_speed_x), 90)
  assert.equal(value(result.machine_max_acceleration_x), 1200)
  assert.equal(machine.machine_max_speed_x[0], 100)
  assert.deepEqual(result.nozzle_diameter, [0.4])
})

test('original end G-code parking speed is slowed without losing Flashforge commands', () => {
  const original = 'G1 E-3 F3600\\nG0 X50 Y50 F9000\\nM652\\nG28 X Y'
  const result = applyAd4SafeMachineLimits({ machine_end_gcode: original })
  assert.ok(result.machine_end_gcode.includes('G1 E-3 F2400'))
  assert.ok(result.machine_end_gcode.includes('G0 X50 Y50 F4800'))
  assert.ok(result.machine_end_gcode.includes('M652'))
  assert.equal(original.includes('F9000'), true)
})
