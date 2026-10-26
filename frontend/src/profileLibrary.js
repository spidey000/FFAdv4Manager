// Custom presets are saved in this browser only; no printer/backend API is involved.
// A custom process contains only process keys, and a custom material only filament keys.
// Keeping the snapshots disjoint prevents changing a material from resetting motion settings.

export const PROFILE_STORAGE_KEY = 'threeslicer.ad4.profile-library.v1'
export const SAVE_PROCESS_OPTION = '__save_new_process_profile__'
export const SAVE_FILAMENT_OPTION = '__save_new_filament_profile__'
export const ARTILLERY_PLA_BASIC = 'Artillery PLA Basic @Flashforge AD4'
export const MAX_CUSTOM_PROFILES = 40

export const emptyProfileLibrary = () => ({ process: [], filament: [] })

export function browserProfileStorage() {
  try { return typeof window === 'undefined' ? null : window.localStorage }
  catch { return null }
}

const validType = type => type === 'process' || type === 'filament'
const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const cleanName = name => typeof name === 'string' ? name.trim().replace(/\s+/g, ' ') : ''
const sameName = (a, b) => a.toLocaleLowerCase() === b.toLocaleLowerCase()

export function snapshotPreset(settings, keys) {
  const result = {}
  if (!isRecord(settings) || !Array.isArray(keys)) return result
  for (const key of keys) {
    if (typeof key !== 'string' || !Object.hasOwn(settings, key)) continue
    const value = settings[key]
    if (value !== undefined) result[key] = structuredClone(value)
  }
  return result
}

export function readProfileLibrary(storage) {
  const empty = emptyProfileLibrary()
  try {
    const parsed = JSON.parse(storage?.getItem(PROFILE_STORAGE_KEY) || 'null')
    if (!isRecord(parsed) || parsed.version !== 1) return empty
    for (const type of ['process', 'filament']) {
      if (!Array.isArray(parsed[type])) continue
      empty[type] = parsed[type].filter(item =>
        isRecord(item) && typeof item.name === 'string' && cleanName(item.name).length > 0 &&
        cleanName(item.name).length <= 80 && isRecord(item.values)
      ).slice(0, MAX_CUSTOM_PROFILES).map(item => ({
        name: cleanName(item.name), values: item.values,
      }))
    }
  } catch { /* Browser storage may be blocked or contain legacy/corrupt JSON. */ }
  return empty
}

export function writeProfileLibrary(storage, library) {
  if (!storage || typeof storage.setItem !== 'function') {
    throw new Error('Local profile storage is not available in this browser.')
  }
  storage.setItem(PROFILE_STORAGE_KEY, JSON.stringify({ version: 1, ...library }))
}

export function addCustomProfile(library, type, name, settings, keys, builtInNames = []) {
  if (!validType(type)) throw new Error('Unknown profile type.')
  const title = cleanName(name)
  if (title.length < 2 || title.length > 80 || /[<>\x00-\x1f]/.test(title)) {
    throw new Error('Use a profile name between 2 and 80 characters.')
  }
  const items = library[type]
  if (items.length >= MAX_CUSTOM_PROFILES) throw new Error('The custom profile limit has been reached.')
  if ([...builtInNames, ...items.map(p => p.name)].some(item => sameName(item, title))) {
    throw new Error('This name is already used. Choose another name.')
  }
  const values = snapshotPreset(settings, keys)
  if (!Object.keys(values).length) throw new Error('No editable settings were found to save.')
  return { ...library, [type]: [...items, { name: title, values }] }
}

export function replaceCustomProfile(library, type, name, settings, keys) {
  if (!validType(type)) throw new Error('Unknown profile type.')
  const index = library[type].findIndex(p => p.name === name)
  if (index < 0) throw new Error('This custom profile was not found.')
  const values = snapshotPreset(settings, keys)
  if (!Object.keys(values).length) throw new Error('No editable settings were found to save.')
  return {
    ...library,
    [type]: library[type].map((profile, i) => i === index ? { ...profile, values } : profile),
  }
}

export function removeCustomProfile(library, type, name) {
  if (!validType(type)) throw new Error('Unknown profile type.')
  return { ...library, [type]: library[type].filter(p => p.name !== name) }
}

export function makeArtilleryPlaBasic(genericPla) {
  if (!isRecord(genericPla)) throw new Error('Generic PLA profile is unavailable.')
  return {
    ...genericPla,
    filament_vendor: ['Artillery'],
    filament_type: ['PLA'],
    filament_flow_ratio: [1.0], // Initial uncalibrated baseline, NOT a measured flow correction.
    filament_max_volumetric_speed: [10], // Cautious AD4 starting value, not Artillery's maximum.
    filament_diameter: [1.75],
    filament_density: [1.24],
    nozzle_temperature: [205],
    nozzle_temperature_initial_layer: [210],
    nozzle_temperature_range_low: [190],
    nozzle_temperature_range_high: [220],
    cool_plate_temp: [55],
    cool_plate_temp_initial_layer: [55],
    eng_plate_temp: [55],
    eng_plate_temp_initial_layer: [55],
    hot_plate_temp: [55],
    hot_plate_temp_initial_layer: [55],
    textured_plate_temp: [55],
    textured_plate_temp_initial_layer: [55],
    fan_max_speed: [100],
    fan_min_speed: [30],
    enable_pressure_advance: false, // Stock Generic PLA has PA=0.8; not calibrated for Artillery.
    pressure_advance: [0],
  }
}
