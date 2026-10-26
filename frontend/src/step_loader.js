// Optional STEP support, matching the upstream demo: OCCT loads only when a STEP file is opened.
import { registerLoader } from 'three-slicer-viewer/loaders'

let occtPromise
const getOcct = () => (occtPromise ||= (async () => {
  const [{ default: occtImportJs }, { default: wasmUrl }] = await Promise.all([
    import('occt-import-js'),
    import('occt-import-js/dist/occt-import-js.wasm?url'),
  ])
  return occtImportJs({ locateFile: () => wasmUrl })
})())

registerLoader('step,stp', async (buffer, name) => {
  const occt = await getOcct()
  const result = occt.ReadStepFile(new Uint8Array(buffer), null)
  if (!result?.success) throw new Error('No se pudo leer el archivo STEP')
  const models = []
  for (const mesh of result.meshes || []) {
    const positions = mesh.attributes?.position?.array
    const indices = mesh.index?.array
    if (!positions || !indices || indices.length < 3) continue
    const triangles = new Float32Array(indices.length * 3)
    for (let i = 0; i < indices.length; i++) {
      const offset = indices[i] * 3
      triangles[i * 3] = positions[offset]
      triangles[i * 3 + 1] = positions[offset + 1]
      triangles[i * 3 + 2] = positions[offset + 2]
    }
    models.push({ name: result.meshes.length > 1 ? `${name}#${models.length + 1}` : name, modelPos: triangles })
  }
  return models
})
