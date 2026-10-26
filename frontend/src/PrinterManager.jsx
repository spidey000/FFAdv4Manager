import { useEffect, useRef, useState } from 'react'
import './printer-manager.css'

const ENDPOINT = '/api/printer'
const ACTIVE = new Set(['BUILDING', 'BUILDING_FROM_SD', 'PRINTING'])
const PAUSED = new Set(['PAUSED'])
async function api(path, options) {
  let response
  try { response = await fetch(ENDPOINT + path, { cache: 'no-store', ...options }) }
  catch { throw new Error('No se puede contactar con el puente local') }
  const result = await response.json().catch(() => null)
  if (!response.ok) throw new Error(result?.error || 'El puente local no está disponible (HTTP ' + response.status + ')')
  return result
}
function post(path, data) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
}
function Icon({ name, size = 19 }) {
  const paths = {
    printer: <><rect x="5" y="2" width="14" height="7" rx="2"/><rect x="3" y="9" width="18" height="11" rx="2"/><path d="M7 16h10v6H7z"/></>,
    back: <path d="m15 18-6-6 6-6M9 12h12"/>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5 9a8 8 0 0 1 14-2l1 5M19 15a8 8 0 0 1-14 2l-1-5"/></>,
    thermometer: <><path d="M10 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0Z"/><path d="M13 8v10"/></>,
    file: <><path d="M6 2h8l5 5v15H6zM14 2v6h5M9 13h7M9 17h7"/></>,
    play: <path d="m7 4 14 8-14 8z"/>,
    pause: <><path d="M7 4v16M17 4v16"/></>,
    stop: <rect x="5" y="5" width="14" height="14" rx="1"/>,
    camera: <><path d="M3 7h4l2-3h6l2 3h4v14H3z"/><circle cx="12" cy="14" r="4"/></>,
    wifi: <><path d="M2 9a15 15 0 0 1 20 0M5 13a10 10 0 0 1 14 0M9 17a5 5 0 0 1 6 0"/><circle cx="12" cy="21" r="1"/></>,
    fan: <><circle cx="12" cy="12" r="2"/><path d="M12 10C8 2 3 4 5 8c1 2 3 3 5 4M14 12c8-4 6-9 2-7-2 1-3 3-4 5M12 14c4 8 9 6 7 2-1-2-3-3-5-4M10 12c-8 4-6 9-2 7 2-1 3-3 4-5"/></>,
    pulse: <path d="M2 12h4l3-7 5 14 3-7h5"/>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 9h18c0-1-3-2-3-9M10 21h4"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/></>,
    network: <><circle cx="12" cy="4" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M12 6v5M12 11l-7 6M12 11l7 6"/></>,
  }
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.printer}</svg>
}
function Card({ icon, title, right, children }) {
  return <section className="pm-card"><header className="pm-card-head"><span className="pm-card-heading"><span className="pm-icon"><Icon name={icon}/></span><h3>{title}</h3></span>{right}</header>{children}</section>
}
const temp = v => v == null ? '—' : String(v) + '°C'
const text = v => v == null || v === '' ? '—' : String(v)
const statusLabel = s => ({ READY: 'Lista', PAUSED: 'Pausada', BUILDING: 'Imprimiendo', BUILDING_FROM_SD: 'Imprimiendo', PRINTING: 'Imprimiendo' })[s] || s || 'Sin conexión'
const fileName = p => String(p).split('/').pop()
const encode = name => encodeURIComponent(name)

export default function PrinterManager({ onClose }) {
  const [session, setSession] = useState(null)
  const [state, setState] = useState(null)
  const [bridge, setBridge] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')
  const [devices, setDevices] = useState([])
  const [files, setFiles] = useState([])
  const [profiles, setProfiles] = useState([])
  const [profileName, setProfileName] = useState('')
  const [profileHost, setProfileHost] = useState('')
  const [diagnostic, setDiagnostic] = useState(null)
  const [camera, setCamera] = useState('')
  const [cameraError, setCameraError] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [timelapse, setTimelapse] = useState(null)
  const cameraUrl = useRef('')
  const fileInput = useRef(null)

  async function refreshStatus() {
    try { setState(await api('/status')) }
    catch (e) { setState(null); setError(e.message) }
  }
  async function refreshAll() {
    try {
      const s = await api('/session')
      setSession(s); setBridge(true); setError('')
      const results = await Promise.allSettled([api('/status'), api('/files'), api('/profiles'), api('/timelapse')])
      if (results[0].status === 'fulfilled') setState(results[0].value)
      else { setState(null); setError(results[0].reason.message) }
      setFiles(results[1].status === 'fulfilled' ? results[1].value : [])
      setProfiles(results[2].status === 'fulfilled' ? results[2].value : [])
      if (results[3].status === 'fulfilled') setTimelapse(results[3].value)
    } catch {
      setBridge(false); setState(null); setFiles([]); setProfiles([])
      setError('Este sitio no tiene conexión con el puente local. GitHub Pages solo permite laminar; inicia npm run local en el equipo conectado a la impresora.')
    }
  }
  useEffect(() => {
    refreshAll()
    const timer = setInterval(() => { refreshStatus(); api('/session').then(setSession).catch(() => {}); api('/timelapse').then(setTimelapse).catch(() => {}) }, 8000)
    const key = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', key)
    return () => { clearInterval(timer); document.removeEventListener('keydown', key); if (cameraUrl.current) URL.revokeObjectURL(cameraUrl.current) }
  }, [])
  const running = Boolean(state && ACTIVE.has(state.machine_status))
  const paused = Boolean(state && PAUSED.has(state.machine_status))
  const available = bridge && Boolean(state)
  const rawProgress = state?.progress_percent ?? (state?.sd_total > 0 ? state.sd_current / state.sd_total * 100 : null)
  const progress = typeof rawProgress === 'number' && Number.isFinite(rawProgress) ? Math.max(0, Math.min(100, Math.round(rawProgress))) : null

  async function run(key, work, after) {
    if (busy) return
    setBusy(key); setNotice(''); setError('')
    try { const result = await work(); setNotice('Operación completada: ' + key); if (after) await after(result); return result }
    catch (e) { setError(e.message) }
    finally { setBusy('') }
  }
  function action(key, payload, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return
    run(key, () => post('/actions', payload), refreshAll)
  }
  async function discover() {
    await run('Descubrimiento', () => api('/discover'), data => setDevices(data))
  }
  async function capture() {
    await run('Captura', async () => {
      const response = await fetch(ENDPOINT + '/camera', { cache: 'no-store' })
      if (!response.ok) throw new Error('No se pudo obtener la fotografía')
      const blob = await response.blob()
      return URL.createObjectURL(blob)
    }, url => {
      if (cameraUrl.current) URL.revokeObjectURL(cameraUrl.current)
      cameraUrl.current = url; setCamera(url); setCameraError('')
    })
  }
  async function sendFile(start) {
    if (!selectedFile) { fileInput.current?.click(); return }
    if (start && !window.confirm('¿Enviar e iniciar la impresión de ' + selectedFile.name + '? Comprueba físicamente la impresora.')) return
    await run(start ? 'Subir e imprimir' : 'Subir archivo', async () => {
      const response = await fetch(ENDPOINT + '/upload?start=' + start + '&name=' + encode(selectedFile.name), {
        method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: selectedFile,
      })
      const result = await response.json().catch(() => null)
      if (!response.ok) throw new Error(result?.error || 'Error al enviar el archivo')
      return result
    }, () => { setSelectedFile(null); if (fileInput.current) fileInput.current.value = ''; return refreshAll() })
  }
  const profileSelection = session?.profile || null
  return <div className="pm-overlay" role="dialog" aria-modal="true" aria-labelledby="pm-title">
    <div className="pm-window">
      <header className="pm-header"><button className="pm-back" type="button" onClick={onClose} aria-label="Volver al laminador"><Icon name="back"/></button>
        <div className="pm-title"><span>CONTROL LOCAL</span><h2 id="pm-title">Gestión de impresora</h2><small>FlashForge Adventurer 4 · FFAD4Manager</small></div>
        <span className={'pm-connection ' + (available ? 'online' : '')}><span className="pm-dot"/>{available ? statusLabel(state.machine_status) : 'Sin conexión'}</span>
      </header>
      <div className="pm-body">
        {(error || notice) && <div role={error ? 'alert' : 'status'} className={'pm-message ' + (error ? 'is-error' : '')}>{error || notice}</div>}
        <div className="pm-grid">
          <Card icon="printer" title="Estado de impresora" right={<button className="pm-icon-button" disabled={!bridge || !!busy} title="Actualizar estado" onClick={refreshAll}><Icon name="refresh"/></button>}>
            <p className="pm-subtle">Adventurer 4 · {session?.profile ? 'Perfil: ' + session.profile : session?.host ? 'IP: ' + session.host : 'Conexión configurada en el CLI'}</p>
            <div className="pm-metrics"><div><span>Boquilla</span><strong>{temp(state?.nozzle_current)}</strong><small>Objetivo {temp(state?.nozzle_target)}</small></div>
              <div><span>Cama</span><strong>{temp(state?.bed_current)}</strong><small>Objetivo {temp(state?.bed_target)}</small></div>
              <div><span>Estado</span><strong>{statusLabel(state?.machine_status)}</strong><small>{text(state?.move_mode)}</small></div></div>
          </Card>
          <Card icon="file" title="Trabajo actual">
            <p className="pm-job-name">{state?.current_file || 'No hay un trabajo identificado'}</p>
            <div className="pm-job-progress"><div className="pm-progress"><span style={{ width: (progress ?? 0) + '%' }}/></div><strong>{progress == null ? '—' : progress + '%'}</strong></div>
            <p className="pm-subtle">Capas: {text(state?.layer_current)} / {text(state?.layer_total)} · Progreso informado por la impresora</p>
            <div className="pm-actions three">
              <button type="button" disabled={!running || !!busy} onClick={() => action('Pausar', { action: 'pause' })}><Icon name="pause"/>Pausar</button>
              <button type="button" disabled={!paused || !!busy} onClick={() => action('Reanudar', { action: 'resume' })}><Icon name="play"/>Reanudar</button>
              <button type="button" className="pm-danger" disabled={!(running || paused) || !!busy} onClick={() => action('Cancelar', { action: 'cancel' }, '¿Cancelar la impresión actual? Esta acción puede descartar el trabajo.') }><Icon name="stop"/>Cancelar</button>
            </div>
          </Card>
          <Card icon="network" title="Descubrir impresoras" right={<button className="pm-small" disabled={!bridge || !!busy} onClick={discover}><Icon name="refresh"/> Buscar</button>}>
            <p className="pm-subtle">Detecta dispositivos anunciados en la red del equipo que ejecuta el puente.</p>
            {devices.length ? <div className="pm-list">{devices.map(d => <div className="pm-list-item" key={d.ip}><div><strong>{d.name || 'Impresora'}</strong><small>{d.ip} · puerto {d.port}</small></div>
              <button type="button" className="pm-small" disabled={!!busy || !bridge || d.port !== 8899 || (session?.host === d.ip && !profileSelection)} onClick={() => run('Conectar', () => post('/selection', { host: d.ip }), async () => { setCamera(''); await refreshAll() })}>{session?.host === d.ip && !profileSelection ? 'Conectada' : 'Conectar'}</button></div>)}</div> : <p className="pm-empty">Pulsa Buscar para localizar impresoras.</p>}
          </Card>
          <Card icon="file" title="Archivos de la impresora" right={<button type="button" className="pm-small" disabled={!bridge || !!busy} onClick={() => run('Actualizar archivos', () => api('/files'), setFiles)}>Actualizar</button>}>
            {files.length ? <div className="pm-list">{files.map(f => <div className="pm-list-item" key={f}><div><strong title={f}>{fileName(f)}</strong><small>{f}</small></div>
              <button className="pm-small" type="button" disabled={!available || running || paused || !!busy} onClick={() => action('Imprimir archivo', { action: 'print', file: f }, '¿Imprimir el archivo almacenado ' + fileName(f) + '? Comprueba el material y la impresora.') }><Icon name="play"/> Imprimir</button></div>)}</div> : <p className="pm-empty">{bridge ? 'No se han encontrado archivos o aún no se ha consultado el almacenamiento.' : 'Requiere el puente local.'}</p>}
          </Card>
          <Card icon="camera" title="Cámara" right={<button className="pm-small" type="button" disabled={!bridge || !!busy} onClick={capture}><Icon name="camera"/> Capturar</button>}>
            {camera ? <img className="pm-camera-image" src={camera} alt="Última captura real de la cámara de la impresora"/> : <div className="pm-camera-empty"><Icon name="camera" size={32}/><span>Sin fotografía · Captura bajo demanda</span></div>}
            {cameraError && <p className="pm-subtle">{cameraError}</p>}
            <p className="pm-subtle">Fotograma JPEG, no vídeo en directo.</p>
          </Card>
          <Card icon="fan" title="Ventilador de capa">
            <p className="pm-subtle">El CLI permite únicamente encender al 100% o apagar el ventilador de capa. No controla el ventilador de la carcasa ni informa de su velocidad.</p>
            <div className="pm-actions"><button disabled={!available || !!busy} onClick={() => action('Encender ventilador', { action: 'fan_on' })}>Encender</button>
              <button disabled={!available || !!busy} onClick={() => action('Apagar ventilador', { action: 'fan_off' })}>Apagar</button></div>
          </Card>
          <Card icon="pulse" title="Diagnósticos">
            <div className="pm-actions pm-wrap">{[['doctor','Comprobar'],['info','Firmware / identidad'],['position','Posición']].map(([kind,label]) =>
              <button key={kind} disabled={!bridge || !!busy} onClick={() => run(label, () => api('/diagnostics?kind=' + kind), setDiagnostic)}>{label}</button>)}</div>
            {diagnostic && <pre className="pm-diagnostic">{typeof diagnostic.output === 'string' ? diagnostic.output : JSON.stringify(diagnostic.output, null, 2)}</pre>}
          </Card>
          <Card icon="camera" title="Timelapse">
            <p className="pm-subtle">Serie de 20 capturas JPEG, separadas 10 segundos. Guardadas en el equipo del puente, no por capas.</p>
            <p className="pm-subtle">Capturas: {timelapse?.frames ?? 0} · {timelapse?.running ? 'En curso' : 'Detenido'}</p>
            <div className="pm-actions"><button disabled={!bridge || !!busy || timelapse?.running} onClick={() => run('Iniciar timelapse', () => post('/timelapse', { action: 'start' }), setTimelapse)}>Iniciar</button>
              <button disabled={!bridge || !!busy || !timelapse?.running} onClick={() => run('Detener timelapse', () => post('/timelapse', { action: 'stop' }), setTimelapse)}>Detener</button></div>
          </Card>
          <Card icon="bell" title="Notificaciones del CLI">
            <p className="pm-subtle">Avisos de escritorio en el ordenador Linux del puente (notify-send): pausa, desconexión, impresión y listo. No son notificaciones push al móvil.</p>
            <div className="pm-actions"><button disabled={!bridge || !!busy || session?.notifying} onClick={() => run('Activar avisos', () => post('/notifications', { action: 'start' }), refreshAll)}>Activar</button>
              <button disabled={!bridge || !!busy || !session?.notifying} onClick={() => run('Desactivar avisos', () => post('/notifications', { action: 'stop' }), refreshAll)}>Detener</button></div>
          </Card>
          <Card icon="layers" title="Perfiles de conexión">
            <p className="pm-subtle">Perfiles de host/IP del CLI. No modifican los presets de calidad del laminador.</p>
            {profiles.length ? <div className="pm-list">{profiles.map(p => <div key={p} className="pm-list-item"><div><strong>{p}</strong><small>{profileSelection === p ? 'Activo' : 'Perfil del CLI'}</small></div>
              <div className="pm-inline"><button className="pm-small" disabled={!!busy || profileSelection === p} onClick={() => run('Seleccionar perfil', () => post('/selection', { profile: p }), async () => { setCamera(''); await refreshAll() })}>Usar</button>
                <button className="pm-small pm-danger" disabled={!!busy} onClick={() => { if (window.confirm('¿Eliminar el perfil de conexión ' + p + '?')) run('Eliminar perfil', () => post('/profiles/delete', { name: p }), refreshAll) }}>×</button></div></div>)}</div> : <p className="pm-empty">No hay perfiles guardados.</p>}
            <div className="pm-inputs"><input maxLength={64} aria-label="Nombre del perfil" placeholder="Nombre del perfil" value={profileName} onChange={e => setProfileName(e.target.value)}/><input inputMode="decimal" aria-label="IP local de la impresora" placeholder="IP local (192.168.x.x)" value={profileHost} onChange={e => setProfileHost(e.target.value)}/></div>
            <button className="pm-small" disabled={!bridge || !!busy || !profileName.trim() || !profileHost.trim()} onClick={() => run('Guardar perfil', () => post('/profiles', { name: profileName, host: profileHost }), async () => { setProfileName(''); setProfileHost(''); await refreshAll() })}>+ Guardar perfil</button>
          </Card>
          <Card icon="upload" title="Subir G-code o GX">
            <p className="pm-subtle">Elige un archivo de hasta 100 MB. El CLI convierte G-code a GX cuando corresponde.</p>
            <input ref={fileInput} className="pm-hidden-input" type="file" accept=".gx,.gcode,.gco,.g" onChange={e => setSelectedFile(e.target.files?.[0] || null)}/>
            <button className="pm-pick" disabled={!bridge || !!busy} onClick={() => fileInput.current?.click()}>{selectedFile?.name || 'Seleccionar archivo…'}</button>
            <div className="pm-actions"><button disabled={!available || !selectedFile || !!busy} onClick={() => sendFile(false)}><Icon name="upload"/> Solo subir</button>
              <button className="pm-primary" disabled={!available || !selectedFile || !!busy} onClick={() => sendFile(true)}><Icon name="play"/> Subir e imprimir</button></div>
            <p className="pm-subtle">Supervisa la impresora: el modo «solo subir» evita solicitar M23/M24, pero el firmware puede tener efectos no documentados.</p>
          </Card>
        </div>
      </div>
    </div>
  </div>
}
