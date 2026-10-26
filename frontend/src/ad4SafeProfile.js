// Conservative quality profile for the *standard* Flashforge Adventurer 4, 0.4 mm nozzle.
// This is a deliberately cautious local preset, NOT a manufacturer-certified firmware limit.
// FlashPrint's standard 60 mm/s print / 80 mm/s travel and Flashforge's <=60 mm/s advice
// for small models informed the speed envelope; accelerations are conservative estimates.
// Values use OrcaSlicer's parameter names and the types supplied by three-slicer@0.4.0.

export const AD4_STOCK_PROCESS = '0.20mm Standard @Flashforge AD4 0.4 Nozzle'
export const AD4_SAFE_PROCESS = '0.20mm Quality (Conservative) @Flashforge AD4 0.4 Nozzle'

export const AD4_SAFE_MACHINE_LIMITS = Object.freeze({
  // Machine ceilings are also used by the time estimator. These do not rewrite firmware.
  machine_max_speed_x: [90],
  machine_max_speed_y: [90],
  machine_max_acceleration_x: [1200],
  machine_max_acceleration_y: [1200],
  machine_max_acceleration_extruding: [1200],
  machine_max_acceleration_travel: [1200],
  machine_max_acceleration_retracting: [1500],
  machine_max_jerk_x: [7],
  machine_max_jerk_y: [7],
})

export const AD4_SAFE_PROCESS_OVERRIDES = Object.freeze({
  initial_layer_speed: [20],
  initial_layer_infill_speed: [25],
  initial_layer_travel_speed: '70',
  outer_wall_speed: [35],
  inner_wall_speed: [50],
  sparse_infill_speed: [55],
  internal_solid_infill_speed: [45],
  top_surface_speed: [30],
  gap_infill_speed: [30],
  support_speed: [50],
  support_interface_speed: [40],
  travel_speed: [80],
  bridge_speed: [25],
  skirt_speed: 20,
  small_perimeter_speed: '50%',
  ironing_speed: 15,
  // Orca parameters not implemented by the engine (e.g. overhang_N_4_speed)
  // are deliberately not presented as functional overrides.
  default_acceleration: [800],
  initial_layer_acceleration: [300],
  outer_wall_acceleration: [450],
  inner_wall_acceleration: [700],
  sparse_infill_acceleration: [800],
  internal_solid_infill_acceleration: '650',
  top_surface_acceleration: [400],
  bridge_acceleration: [500],
  initial_layer_travel_acceleration: [500],
  travel_acceleration: [1000],
})

export function applyAd4SafeMachineLimits(printerPreset) {
  // The upstream printer's end G-code parks at F9000 = 150 mm/s regardless
  // of the process travel setting. Keep Flashforge commands intact; only slow
  // down the two explicit end-of-print feedrates for the conservative default.
  const endGcode = typeof printerPreset?.machine_end_gcode === 'string'
    ? printerPreset.machine_end_gcode
      .replace('G1 E-3 F3600', 'G1 E-3 F2400')
      .replace('G0 X50 Y50 F9000', 'G0 X50 Y50 F4800')
    : printerPreset?.machine_end_gcode
  return {
    ...printerPreset,
    ...AD4_SAFE_MACHINE_LIMITS,
    ...(endGcode == null ? {} : { machine_end_gcode: endGcode }),
  }
}

export function applyAd4SafeProcess(orcaStandardPreset) {
  if (!orcaStandardPreset) throw new Error('Missing OrcaSlicer standard AD4 process preset')
  return { ...orcaStandardPreset, ...AD4_SAFE_PROCESS_OVERRIDES }
}
