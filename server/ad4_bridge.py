"""Same-origin, loopback-only FFAD4Manager bridge for ThreeSlicer.

The GitHub Pages demo has no printer API. Protected remote access must use
Cloudflare Access JWT verification at this loopback-only origin.
"""
import atexit
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import unicodedata
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ffadv4manager.core.layers import LayerIndex, LayerTracker

if __package__:
    from .cloudflare_access import load_access_config, verify_access_jwt, _jwks_client
else:
    from cloudflare_access import load_access_config, verify_access_jwt, _jwks_client

ACCESS_CONFIG = load_access_config(os.environ)

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'frontend' / 'dist'
BASE = '/'
CLI = os.environ.get('AD4_CLI', 'ffadv4manager')
HOST = os.environ.get('AD4_HOST')
MAX_GCODE = 100 * 1024 * 1024
FILE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,119}\Z')
PROFILE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,63}\Z')
STATE_LOCK = threading.RLock()
SELECTED = {'host': None, 'profile': None}
DISCOVERED = {}
WORKERS = {'timelapse': None, 'notifications': None}
TIMELAPSE_DIR = None
TIMELAPSE_MODE = None
LAYER_TRACKERS = {}
# Per-printer sidecar metadata only: original G-code and GX files are NOT kept.
_STATE_HOME = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local' / 'state')))
LAYER_DIR = Path(os.environ.get('AD4_LAYER_STATE_DIR', str(_STATE_HOME / 'ffadv4manager')))


def _printer_key():
    with STATE_LOCK:
        profile, host = SELECTED['profile'], SELECTED['host']
    return 'profile:' + profile if profile else 'host:' + str(host or HOST or 'configured-cli')


def _index_path(filename):
    # Hash both namespace and basename to avoid arbitrary paths in a filename.
    key = _printer_key() + '\0' + Path(str(filename)).name.casefold()
    return LAYER_DIR / 'layers' / (hashlib.sha256(key.encode('utf-8')).hexdigest() + '.json')


def _save_index(filename, index):
    path = _index_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(6) + '.new')
    temporary.write_text(json.dumps(index.as_dict()), encoding='utf-8')
    temporary.replace(path)


def _load_index(filename):
    if not filename:
        return None
    path = _index_path(filename)
    try:
        return LayerIndex.from_json_file(path)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _augment_status(status):
    """Reusable layer estimate for any API consumer; no phantom layer from M27 0/0."""
    status['layer_estimated_current'] = None
    status['layer_estimated_total'] = None
    status['layer_source'] = 'unavailable'
    status['z_mm'] = None
    if status.get('layer_current') and status.get('layer_total'):
        status['layer_source'] = 'firmware'
        return status
    if status.get('machine_status') not in ('BUILDING', 'BUILDING_FROM_SD', 'PRINTING', 'PAUSED'):
        with STATE_LOCK:
            LAYER_TRACKERS.clear()
        return status
    filename = status.get('current_file')
    index = _load_index(filename)
    if index is None:
        return status
    status['layer_estimated_total'] = len(index.heights)
    status['layer_source'] = 'estimated_z'
    try:
        position = json.loads(command('position', '--json', timeout=12))
        z_mm = position.get('Z')
        if z_mm is None:
            return status
        z_mm = float(z_mm)
        status['z_mm'] = z_mm
        key = (_printer_key(), Path(str(filename)).name.casefold())
        with STATE_LOCK:
            tracked = LAYER_TRACKERS.get(key)
            progress = status.get('progress_percent')
            if (tracked is None or
                    (isinstance(progress, (int, float)) and tracked[1] is not None
                     and progress + 10 < tracked[1])):
                tracker = LayerTracker(index, stable_samples=2)
            else:
                tracker = tracked[0]
            tracker.observe(z_mm)
            LAYER_TRACKERS[key] = (tracker, progress)
            status['layer_estimated_current'] = tracker.layer
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired,
            json.JSONDecodeError):
        pass  # Status must remain available even if M114 cannot be read.
    return status


def _start_timelapse(mode, filename=None):
    global TIMELAPSE_DIR, TIMELAPSE_MODE
    if mode not in ('layer', 'interval'):
        raise ValueError('Modo de timelapse no admitido')
    if not shutil.which('ffmpeg'):
        raise ValueError('Se necesita ffmpeg para generar el vídeo MP4')
    if mode == 'layer':
        if not filename:
            status = json.loads(command('status', '--json'))
            if status.get('machine_status') not in ('BUILDING', 'BUILDING_FROM_SD', 'PRINTING', 'PAUSED'):
                raise ValueError('Inicia una impresión antes del timelapse por capas')
            filename = status.get('current_file')
        if _load_index(filename) is None:
            raise ValueError('No hay índice de capas para este archivo; súbelo desde esta web o usa timelapse por tiempo')
        index_path = _index_path(filename)
    with STATE_LOCK:
        existing = WORKERS['timelapse']
        if existing and existing.poll() is None:
            raise ValueError('Ya existe un timelapse activo')
        folder = LAYER_DIR / 'timelapses' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4))
        folder.mkdir(parents=True, exist_ok=False, mode=0o700)
        arguments = ['camera', 'timelapse', str(folder)]
        if mode == 'layer':
            arguments += ['--on-layer', '--layer-index', str(index_path),
                          '--job-name', Path(str(filename)).name, '--interval', '1.5']
        else:
            arguments += ['--interval', '10', '--count', '20', '--mp4']
        with (folder / 'error.log').open('w', encoding='utf-8') as error_log:
            WORKERS['timelapse'] = subprocess.Popen(
                cli_argv(*arguments), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=error_log)
        TIMELAPSE_DIR = folder
        TIMELAPSE_MODE = mode
    return timelapse_state()




def private_ip(value):
    try:
        ip = ipaddress.ip_address(value)
        return (ip.version == 4 and ip.is_private and not ip.is_loopback
                and not ip.is_link_local and not ip.is_multicast)
    except ValueError:
        return False


def cli_argv(*args, selected=True):
    argv = [CLI]
    if selected:
        with STATE_LOCK:
            profile, host = SELECTED['profile'], SELECTED['host']
        if profile:
            argv += ['--profile', profile]
        elif host or HOST:
            argv += ['--host', host or HOST]
    argv.extend(args)
    return argv


def command(*args, timeout=30, selected=True):
    result = subprocess.run(cli_argv(*args, selected=selected), capture_output=True,
                            text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[:1000]
                           or 'CLI exit ' + str(result.returncode))
    return result.stdout


def safe_filename(name):
    # Do not turn path traversal into a harmless-looking filename. Check the
    # original first, then transliterate common accented model names into ASCII
    # compatible with the FlashForge M28 command grammar.
    if (not isinstance(name, str) or len(name) > 120 or
            any(ch in name for ch in ('/', '\\\\', ':')) or
            any(ord(ch) < 32 or ord(ch) == 127 for ch in name)):
        raise ValueError('Nombre de archivo no válido')
    normalized = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    normalized = re.sub(r'[^A-Za-z0-9_. -]', '_', normalized)
    if not FILE_NAME.fullmatch(normalized) or normalized in ('.', '..'):
        raise ValueError('Nombre de archivo no válido')
    if Path(normalized).suffix.lower() not in ('.gx', '.gcode', '.gco', '.g'):
        raise ValueError('Solo se admiten archivos .gx, .gcode, .gco y .g')
    return normalized


def worker_running(name):
    with STATE_LOCK:
        worker = WORKERS[name]
    return bool(worker and worker.poll() is None)


def timelapse_state():
    with STATE_LOCK:
        folder = TIMELAPSE_DIR
    return {'running': worker_running('timelapse'), 'mode': TIMELAPSE_MODE,
            'frames': len(list(folder.glob('frame-*.jpg'))) if folder and folder.is_dir() else 0,
            'video_ready': bool(folder and (folder / 'timelapse.mp4').is_file())}


def cleanup():
    with STATE_LOCK:
        workers = list(WORKERS.values())
        folder = TIMELAPSE_DIR
    for worker in workers:
        if worker and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=125)
            except subprocess.TimeoutExpired:
                worker.kill()
    # Preserve captures and finalized MP4 after a server shutdown.


atexit.register(cleanup)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def picture(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def request_authorized(self, write=False):
        host = self.headers.get('Host', '').lower()
        origin = self.headers.get('Origin')
        if ACCESS_CONFIG:
            # Access enabled: no loopback authentication bypass. Public requests
            # need the exact Host and a valid signed Access JWT for this user.
            if host != ACCESS_CONFIG['public_host']:
                return False
            if origin and origin != ACCESS_CONFIG['public_origin']:
                return False
            if write and origin != ACCESS_CONFIG['public_origin']:
                return False
            return verify_access_jwt(
                self.headers.get('Cf-Access-Jwt-Assertion'), ACCESS_CONFIG)
        # Development / local-only mode, never accessible from another host.
        if not re.fullmatch(r'(?:localhost|127\.0\.0\.1):\d{1,5}', host):
            return False
        if not write or not origin:
            return True
        return origin in ('http://' + host, 'http://localhost:5173',
                          'http://127.0.0.1:5173')

    def data(self, limit=4096):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= limit:
            raise ValueError('Tamaño de petición no válido')
        if 'application/json' not in self.headers.get('Content-Type', ''):
            raise ValueError('Se requiere JSON')
        return json.loads(self.rfile.read(size))

    def do_HEAD(self):
        # Do not leak static file metadata through an unauthenticated inherited handler.
        self.send_error(405, 'HEAD not supported')

    def do_GET(self):
        if not self.request_authorized():
            return self.json(401 if ACCESS_CONFIG else 403, {'error': 'Unauthorized request'})
        url = urlsplit(self.path)
        path = url.path
        try:
            if path == '/api/printer/session':
                with STATE_LOCK:
                    selection = dict(SELECTED)
                return self.json(200, {**selection, 'notifying': worker_running('notifications')})
            if path == '/api/printer/status':
                return self.json(200, _augment_status(json.loads(command('status', '--json'))))
            if path == '/api/printer/discover':
                devices = json.loads(command('discover', '--json', timeout=12, selected=False))
                if not isinstance(devices, list):
                    raise ValueError('Respuesta de descubrimiento inválida')
                with STATE_LOCK:
                    DISCOVERED.clear()
                    DISCOVERED.update({d['ip']: d.get('port', 8899) for d in devices
                                       if isinstance(d, dict) and private_ip(d.get('ip'))})
                return self.json(200, devices)
            if path == '/api/printer/files':
                return self.json(200, json.loads(command('files', '--json')))
            if path == '/api/printer/profiles':
                return self.json(200, json.loads(command('profiles', 'list', selected=False)))
            if path == '/api/printer/diagnostics':
                kind = parse_qs(url.query).get('kind', ['doctor'])[0]
                if kind not in ('doctor', 'info', 'position'):
                    raise ValueError('Diagnóstico no compatible')
                output = command(kind, *(['--json'] if kind in ('info', 'position') else []), timeout=45)
                return self.json(200, {'output': json.loads(output) if kind != 'doctor' else output})
            if path == '/api/printer/timelapse':
                return self.json(200, timelapse_state())
            if path == '/api/printer/timelapse/video':
                with STATE_LOCK:
                    folder = TIMELAPSE_DIR
                video = folder / 'timelapse.mp4' if folder else None
                if not video or not video.is_file():
                    return self.json(404, {'error': 'Vídeo MP4 no disponible'})
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Disposition', 'attachment; filename="timelapse.mp4"')
                self.send_header('Content-Length', str(video.stat().st_size))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                with video.open('rb') as stream:
                    shutil.copyfileobj(stream, self.wfile)
                return
            if path == '/api/printer/camera':
                with tempfile.TemporaryDirectory() as directory:
                    frame = Path(directory) / 'frame.jpg'
                    command('camera', 'snapshot', str(frame), timeout=25)
                    data = frame.read_bytes()
                return self.picture(data)
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.TimeoutExpired,
                json.JSONDecodeError) as error:
            return self.json(502, {'error': str(error)})
        # Integrated frontend is served at /, and API routes never expose static files.
        if path.startswith('/api/'):
            return self.json(404, {'error': 'Unknown API route'})
        return super().do_GET()

    def do_POST(self):
        global TIMELAPSE_DIR
        url = urlsplit(self.path)
        path = url.path
        if path not in ('/api/printer/jobs', '/api/printer/upload', '/api/printer/actions',
                        '/api/printer/selection', '/api/printer/profiles',
                        '/api/printer/profiles/delete', '/api/printer/timelapse',
                        '/api/printer/notifications'):
            return self.send_error(404)
        if not self.request_authorized(write=True):
            return self.json(401 if ACCESS_CONFIG else 403, {'error': 'Unauthorized request'})
        try:
            if path in ('/api/printer/jobs', '/api/printer/upload'):
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_GCODE:
                    return self.json(413, {'error': 'Archivo vacío o superior a 100 MB'})
                legacy = path.endswith('/jobs')
                expected_type = 'text/plain' if legacy else 'application/octet-stream'
                if not self.headers.get('Content-Type', '').startswith(expected_type):
                    return self.json(415, {'error': 'Tipo de archivo no admitido'})
                data = self.rfile.read(size)
                if len(data) != size or not data.strip(b'\x00\r\n\t '):
                    raise ValueError('Archivo vacío o incompleto')
                # Preserve the real source name supplied by the slicer or file picker.
                # Never silently replace an uploaded model with a generic filename.
                try:
                    name = safe_filename(parse_qs(url.query).get('name', [''])[0])
                except ValueError as exc:
                    return self.json(400, {'error': str(exc)})
                start = parse_qs(url.query).get('start', ['false'])[0] == 'true'
                auto_layers = parse_qs(url.query).get('timelapse', [''])[0] == 'layer'
                if auto_layers and not start:
                    raise ValueError('El timelapse automático requiere iniciar impresión')
                if auto_layers and worker_running('timelapse'):
                    raise ValueError('Ya existe un timelapse activo')
                if auto_layers and not shutil.which('ffmpeg'):
                    raise ValueError('Se necesita ffmpeg para el vídeo de timelapse')
                with tempfile.TemporaryDirectory() as directory:
                    filename = Path(directory) / name
                    filename.write_bytes(data)
                    try:
                        layer_index = LayerIndex.from_file(filename)
                    except (OSError, ValueError):
                        layer_index = None
                    if auto_layers and layer_index is None:
                        raise ValueError('El archivo no contiene capas detectables')
                    output = command('upload', str(filename), *(['--start'] if start else []), timeout=3600)
                # The CLI chooses the printer filename using GX header metadata;
                # report the actual destination returned by the CLI, not the
                # temporary name used to pass the file to the converter.
                match = re.search(r'Uploaded and listed:\s*([^\r\n]+)', output)
                if not match:
                    raise RuntimeError('The CLI did not report a confirmed remote upload')
                remote_path = match.group(1).strip()
                if layer_index is not None:
                    _save_index(remote_path, layer_index)
                if auto_layers:
                    _start_timelapse('layer', remote_path)
                return self.json(200, {'remote_name': remote_path.rsplit('/', 1)[-1],
                                       'remote_path': remote_path, 'started': start,
                                       'indexed_layers': len(layer_index.heights) if layer_index else None,
                                       'detail': output[-1000:]})
            body = self.data()
            if not isinstance(body, dict):
                raise ValueError('Formato JSON no válido')
            if path == '/api/printer/actions':
                action = body.get('action')
                simple = {'pause': ('pause',), 'resume': ('resume',), 'cancel': ('cancel',),
                          'fan_on': ('fan', 'on'), 'fan_off': ('fan', 'off')}
                if action == 'print':
                    filename = body.get('file')
                    listed = json.loads(command('files', '--json'))
                    if not isinstance(filename, str) or filename not in listed:
                        raise ValueError('El archivo no está en el listado actual')
                    if body.get('timelapse_on_start') is True:
                        if worker_running('timelapse') or _load_index(filename) is None:
                            raise ValueError('Timelapse por capas no disponible: sube primero este archivo o detén el timelapse actual')
                    output = command('print', filename, timeout=50)
                    if body.get('timelapse_on_start') is True:
                        _start_timelapse('layer', filename)
                elif action in simple:
                    output = command(*simple[action], timeout=50)
                else:
                    raise ValueError('Acción no admitida')
                return self.json(200, {'detail': output[-1000:]})
            if path == '/api/printer/selection':
                profile = body.get('profile')
                host = body.get('host')
                if bool(profile) == bool(host):
                    raise ValueError('Selecciona un host o un perfil')
                if profile:
                    profiles = json.loads(command('profiles', 'list', selected=False))
                    if profile not in profiles:
                        raise ValueError('Perfil inexistente')
                    with STATE_LOCK:
                        SELECTED.update(profile=profile, host=None)
                else:
                    with STATE_LOCK:
                        eligible = DISCOVERED.get(host) == 8899
                    if not private_ip(host) or not eligible:
                        raise ValueError('Selecciona una impresora descubierta con puerto 8899')
                    with STATE_LOCK:
                        SELECTED.update(host=host, profile=None)
                return self.json(200, dict(SELECTED))
            if path == '/api/printer/profiles':
                name, host = body.get('name'), body.get('host')
                if not isinstance(name, str) or not PROFILE_NAME.fullmatch(name):
                    raise ValueError('Nombre de perfil inválido')
                if not isinstance(host, str) or not private_ip(host):
                    raise ValueError('Se requiere una IPv4 privada válida')
                command('profiles', 'add', name, '--host', host, selected=False)
                return self.json(200, {'added': name})
            if path == '/api/printer/profiles/delete':
                name = body.get('name')
                if not isinstance(name, str) or not PROFILE_NAME.fullmatch(name):
                    raise ValueError('Perfil inválido')
                command('profiles', 'delete', name, selected=False)
                with STATE_LOCK:
                    if SELECTED['profile'] == name:
                        SELECTED.update(host=None, profile=None)
                return self.json(200, {'deleted': name})
            if path == '/api/printer/timelapse':
                action = body.get('action')
                if action == 'start':
                    return self.json(200, _start_timelapse(body.get('mode', 'interval')))
                if action != 'stop':
                    raise ValueError('Acción de timelapse inválida')
                with STATE_LOCK:
                    worker = WORKERS['timelapse']
                if worker and worker.poll() is None:
                    worker.terminate()
                    worker.wait(timeout=125)  # SIGTERM causes MP4 finalization.
                return self.json(200, timelapse_state())
            if path == '/api/printer/notifications':
                action = body.get('action')
                with STATE_LOCK:
                    worker = WORKERS['notifications']
                    if action == 'stop':
                        if worker and worker.poll() is None:
                            worker.terminate()
                    elif action == 'start':
                        if not shutil.which('notify-send'):
                            raise ValueError('notify-send no está instalado en el equipo Linux')
                        if not worker or worker.poll() is not None:
                            WORKERS['notifications'] = subprocess.Popen(
                                cli_argv('notify', '--events', 'paused,offline,printing,ready'),
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
                    else:
                        raise ValueError('Acción de notificaciones inválida')
                return self.json(200, {'running': worker_running('notifications')})
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.TimeoutExpired,
                json.JSONDecodeError) as error:
            return self.json(502, {'error': str(error)})


def serve(*, require_access=False):
    """Serve the integrated frontend and API on loopback only."""
    if not (DIST / 'index.html').is_file():
        raise RuntimeError('Missing frontend/dist/: run cd frontend && npm ci && npm run build')
    if require_access and not ACCESS_CONFIG:
        raise RuntimeError('Cloudflare Access configuration is required')
    if ACCESS_CONFIG:
        _jwks_client(ACCESS_CONFIG['jwks_url'])
        print('Cloudflare Access validation enabled: ' + ACCESS_CONFIG['public_origin'], flush=True)
    else:
        print('Local-only mode: Cloudflare authentication disabled; do NOT publish a Tunnel route', flush=True)
    port = int(os.environ.get('AD4_WEB_PORT', '8765'))
    print('FFAdv4Manager: http://127.0.0.1:' + str(port) + '/', flush=True)
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    try:
        serve()
    except (RuntimeError, ValueError) as exc:
        sys.exit(str(exc))
