"""Same-origin, loopback-only FFAD4Manager bridge for ThreeSlicer.

The GitHub Pages demo has no printer API. Protected remote access must use
Cloudflare Access JWT verification at this loopback-only origin.
"""
import atexit
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

if __package__:
    from .cloudflare_access import load_access_config, verify_access_jwt, _jwks_client
else:
    from cloudflare_access import load_access_config, verify_access_jwt, _jwks_client

ACCESS_CONFIG = load_access_config(os.environ)

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
BASE = '/Three_slicer_responsive/'
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
    if not isinstance(name, str) or not FILE_NAME.fullmatch(name) or name in ('.', '..'):
        raise ValueError('Nombre de archivo no válido')
    if Path(name).suffix.lower() not in ('.gx', '.gcode', '.gco', '.g'):
        raise ValueError('Solo se admiten archivos .gx, .gcode, .gco y .g')
    return name


def worker_running(name):
    with STATE_LOCK:
        worker = WORKERS[name]
    return bool(worker and worker.poll() is None)


def timelapse_state():
    with STATE_LOCK:
        folder = TIMELAPSE_DIR
    return {'running': worker_running('timelapse'),
            'frames': len(list(folder.glob('frame-*.jpg'))) if folder and folder.is_dir() else 0}


def cleanup():
    with STATE_LOCK:
        workers = list(WORKERS.values())
        folder = TIMELAPSE_DIR
    for worker in workers:
        if worker and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=3)
            except subprocess.TimeoutExpired:
                worker.kill()
    if folder:
        shutil.rmtree(folder, ignore_errors=True)


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
                return self.json(200, json.loads(command('status', '--json')))
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
            if path == '/api/printer/camera':
                with tempfile.TemporaryDirectory() as directory:
                    frame = Path(directory) / 'frame.jpg'
                    command('camera', 'snapshot', str(frame), timeout=25)
                    data = frame.read_bytes()
                return self.picture(data)
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.TimeoutExpired,
                json.JSONDecodeError) as error:
            return self.json(502, {'error': str(error)})
        if path in ('/', BASE.rstrip('/')):
            self.send_response(302)
            self.send_header('Location', BASE)
            self.end_headers()
            return
        if path.startswith(BASE):
            self.path = '/' + path[len(BASE):]
            return super().do_GET()
        self.send_error(404)

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
                name = 'three-slicer-ad4.gcode' if legacy else safe_filename(
                    unquote(parse_qs(url.query).get('name', [''])[0]))
                start = parse_qs(url.query).get('start', ['false'])[0] == 'true'
                with tempfile.TemporaryDirectory() as directory:
                    filename = Path(directory) / name
                    filename.write_bytes(data)
                    output = command('upload', str(filename), *(['--start'] if start else []), timeout=3600)
                return self.json(200, {'remote_name': name, 'started': start, 'detail': output[-1000:]})
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
                    output = command('print', filename, timeout=50)
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
                with STATE_LOCK:
                    worker = WORKERS['timelapse']
                    if action == 'stop':
                        if worker and worker.poll() is None:
                            worker.terminate()
                        return self.json(200, timelapse_state())
                    if action != 'start':
                        raise ValueError('Acción de timelapse inválida')
                    if worker and worker.poll() is None:
                        raise ValueError('Timelapse ya activo')
                    if TIMELAPSE_DIR:
                        shutil.rmtree(TIMELAPSE_DIR, ignore_errors=True)
                    TIMELAPSE_DIR = Path(tempfile.mkdtemp(prefix='ad4-timelapse-'))
                    WORKERS['timelapse'] = subprocess.Popen(
                        cli_argv('camera', 'timelapse', str(TIMELAPSE_DIR),
                                 '--interval', '10', '--count', '20'),
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
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


if __name__ == '__main__':
    if not (DIST / 'index.html').is_file():
        sys.exit('Missing dist/: run npm run build first')
    if ACCESS_CONFIG:
        _jwks_client(ACCESS_CONFIG['jwks_url'])  # Fail fast if PyJWT is missing.
        print('Cloudflare Access validation enabled: ' + ACCESS_CONFIG['public_origin'], flush=True)
    else:
        print('Local-only mode: Cloudflare authentication disabled', flush=True)
    port = int(os.environ.get('AD4_WEB_PORT', '8765'))
    print('AD4 web: http://127.0.0.1:' + str(port) + BASE, flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
