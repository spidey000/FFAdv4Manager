"""Loopback-bound HTTP bridge for local or Cloudflare Access-protected UI use."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import webbrowser
from urllib.parse import urlsplit

import jwt

HOST = "127.0.0.1"
PORT = 8765
TOKEN_PLACEHOLDER = "__FFADV4MANAGER_TOKEN__"
# Bound request memory while supporting larger (up to 64 MiB) sliced G-code jobs.
MAX_BODY = 64 * 1024 * 1024
BODY_READ_TIMEOUT = 15
CAMERA_SNAPSHOT_TIMEOUT = 20
MAX_SNAPSHOT_REQUEST_BODY = 1024
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.gcode$", re.IGNORECASE)
_ACCESS_ENV = ("CF_ACCESS_TEAM_DOMAIN", "CF_ACCESS_AUD", "CF_ACCESS_EMAIL", "CF_ACCESS_PUBLIC_ORIGIN")


def load_access_config(environ=None, *, required=False):
    """Load complete Cloudflare Access configuration, or preserve local-only mode."""
    environ = os.environ if environ is None else environ
    values = [environ.get(name, "").strip() for name in _ACCESS_ENV]
    if not any(values):
        if required:
            raise RuntimeError("Cloudflare Access is required; set all: " + ", ".join(_ACCESS_ENV))
        return None
    if not all(values):
        raise RuntimeError("Cloudflare Access configuration must set all: " + ", ".join(_ACCESS_ENV))
    domain, audience, email, public_origin = values
    if "/" in domain or ":" in domain or domain.startswith(".") or domain.endswith("."):
        raise RuntimeError("CF_ACCESS_TEAM_DOMAIN must be a hostname without a scheme or path")
    parsed = urlsplit(public_origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or parsed.netloc != parsed.hostname):
        raise RuntimeError("CF_ACCESS_PUBLIC_ORIGIN must be an exact https://hostname origin")
    return {
        "issuer": f"https://{domain}",
        "jwks_url": f"https://{domain}/cdn-cgi/access/certs",
        "audience": audience,
        "email": email,
        "service_token_id": environ.get("CF_ACCESS_SERVICE_TOKEN_ID", "").strip(),
        "public_origin": public_origin,
        "public_host": parsed.hostname,
    }


def verify_access_assertion(assertion: str, config: dict, jwks_client) -> bool:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(assertion)
        claims = jwt.decode(
            assertion,
            signing_key.key,
            algorithms=["RS256"],
            issuer=config["issuer"],
            audience=config["audience"],
            options={"require": ["exp"]},
        )
        email_matches = claims.get("email") == config["email"]
        service_token_id = config.get("service_token_id")
        service_token_matches = bool(service_token_id) and claims.get("common_name") == service_token_id
        return email_matches or service_token_matches
    except Exception:
        return False


def safe_remote_name(filename: str) -> str:
    """Return a safe printer-side basename, rejecting paths and ambiguous names."""
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ValueError("filename must be a plain .gcode basename")
    name = Path(filename).name
    if name != filename or not _SAFE_NAME.fullmatch(name):
        raise ValueError("filename must contain only letters, digits, '.', '_' or '-' and end in .gcode")
    return name


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def validate_print_request(raw: bytes) -> tuple[str, str, bool]:
    """Decode and validate the deliberately narrow print request schema."""
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    if type(data) is not dict or set(data) != {"filename", "gcode", "start"}:
        raise ValueError("Expected exactly filename, gcode, and start fields")
    if type(data["filename"]) is not str or type(data["gcode"]) is not str or type(data["start"]) is not bool:
        raise ValueError("filename and gcode must be strings; start must be boolean")
    if not data["gcode"]:
        raise ValueError("gcode must not be empty")
    return safe_remote_name(data["filename"]), data["gcode"], data["start"]


def invoke_upload(gcode: str, remote_name: str, start: bool) -> subprocess.CompletedProcess:
    """Run this installed project through its module CLI, without a shell."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".gcode", delete=False) as stream:
        path = stream.name
        stream.write(gcode)
    try:
        argv = [sys.executable, "-m", "ffadv4manager.cli", "upload", path, "--remote-name", remote_name]
        if start:
            argv.append("--start")
        return subprocess.run(argv, capture_output=True, text=True, check=False)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def invoke_camera_snapshot() -> bytes:
    """Capture one JPEG through the installed camera CLI, without a shell."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as stream:
        path = stream.name
    try:
        argv = [sys.executable, "-m", "ffadv4manager.cli", "camera", "snapshot", path]
        result = subprocess.run(
            argv, capture_output=True, text=True, check=False, timeout=CAMERA_SNAPSHOT_TIMEOUT,
        )
        if result.returncode:
            raise RuntimeError("Camera snapshot failed")
        image = Path(path).read_bytes()
        if not image.startswith(b"\xff\xd8") or not image.endswith(b"\xff\xd9"):
            raise RuntimeError("Camera snapshot failed")
        return image
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def make_handler(web_root: Path, token: str, upload=invoke_upload, access_config=None, snapshot=invoke_camera_snapshot):
    if access_config is None:
        access_config = load_access_config()
    jwks_client = jwt.PyJWKClient(
        access_config["jwks_url"], cache_jwk_set=True, cache_keys=True, lifespan=300,
        timeout=5, max_cached_keys=16,
    ) if access_config else None
    busy = threading.Lock()
    snapshot_busy = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "FFADV4ManagerSlicer/1"

        def setup(self) -> None:
            self.request.settimeout(BODY_READ_TIMEOUT)
            super().setup()

        def _json(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _authorized_origin(self) -> bool:
            local_host = f"127.0.0.1:{self.server.server_port}"
            local_origin = f"http://127.0.0.1:{self.server.server_port}"
            host, origin = self.headers.get("Host"), self.headers.get("Origin")
            return (host == local_host and origin == local_origin) or bool(
                access_config and host == access_config["public_host"] and origin == access_config["public_origin"]
            )

        def do_GET(self) -> None:
            host = self.headers.get("Host")
            local_host = f"127.0.0.1:{self.server.server_port}"
            public_request = bool(access_config and host == access_config["public_host"])
            if public_request:
                origin = self.headers.get("Origin")
                if origin is not None and origin != access_config["public_origin"]:
                    self.send_error(403)
                    return
                assertion = self.headers.get("Cf-Access-Jwt-Assertion")
                if not assertion or not verify_access_assertion(assertion, access_config, jwks_client):
                    self.send_error(401)
                    return
            elif host != local_host:
                self.send_error(403)
                return
            if self.path == "/":
                relative = "index.html"
            else:
                relative = self.path.split("?", 1)[0].lstrip("/")
            target = (web_root / relative).resolve()
            if not target.is_relative_to(web_root.resolve()) or not target.is_file():
                self.send_error(404)
                return
            try:
                body = target.read_bytes()
                if relative == "index.html":
                    text = body.decode("utf-8")
                    if text.count(TOKEN_PLACEHOLDER) != 1:
                        self.send_error(500, "built index.html must contain exactly one token placeholder")
                        return
                    body = text.replace(TOKEN_PLACEHOLDER, token).encode("utf-8")
            except (OSError, UnicodeError):
                self.send_error(500)
                return
            self.send_response(200)
            content_type = "text/html; charset=utf-8" if target.name == "index.html" else (mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            if relative == "index.html":
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path not in {"/api/print", "/api/camera/snapshot"}:
                self._json(404, {"success": False, "error": "Not found"})
                return
            if not self._authorized_origin():
                self._json(403, {"success": False, "error": "Invalid Host or Origin"})
                return
            if (self.path == "/api/print"
                    and self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"):
                self._json(415, {"success": False, "error": "Content-Type must be application/json"})
                return
            if self.headers.get("Authorization") != f"Bearer {token}":
                self._json(401, {"success": False, "error": "Invalid bearer token"})
                return
            if access_config:
                assertion = self.headers.get("Cf-Access-Jwt-Assertion")
                if not assertion or not verify_access_assertion(assertion, access_config, jwks_client):
                    self._json(401, {"success": False, "error": "Invalid Access assertion"})
                    return
            if self.path == "/api/camera/snapshot":
                if self.headers.get("Transfer-Encoding"):
                    self._json(400, {"success": False, "error": "Request body must be empty"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = -1
                if length < 0 or length > MAX_SNAPSHOT_REQUEST_BODY:
                    self._json(413, {"success": False, "error": "Request body size is invalid or exceeds limit"})
                    return
                try:
                    body = self.rfile.read(length)
                except TimeoutError:
                    self._json(408, {"success": False, "error": "Request body read timed out"})
                    return
                if body.strip():
                    self._json(400, {"success": False, "error": "Request body must be empty"})
                    return
                if not snapshot_busy.acquire(blocking=False):
                    self._json(409, {"success": False, "error": "A camera snapshot is already in progress"})
                    return
                try:
                    try:
                        image = snapshot()
                    except subprocess.TimeoutExpired:
                        self._json(504, {"success": False, "error": "Camera snapshot timed out"})
                        return
                    except Exception:  # noqa: BLE001
                        self._json(502, {"success": False, "error": "Camera snapshot failed"})
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(image)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(image)
                finally:
                    snapshot_busy.release()
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY:
                self._json(413, {"success": False, "error": "Request body size is invalid or exceeds limit"})
                return
            if not busy.acquire(blocking=False):
                self._json(409, {"success": False, "error": "A print request is already in progress"})
                return
            try:
                try:
                    remote_name, gcode, start = validate_print_request(self.rfile.read(length))
                except TimeoutError:
                    self._json(408, {"success": False, "error": "Request body read timed out"})
                    return
                except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
                    self._json(400, {"success": False, "error": str(exc)})
                    return
                try:
                    result = upload(gcode, remote_name, start)
                    if result.returncode:
                        detail = (result.stderr or result.stdout or "Upload failed").strip()
                        self._json(502, {"success": False, "error": detail})
                    else:
                        message = "Upload completed"
                        if start:
                            message += "; print-start command acknowledged; physical printing not verified"
                        self._json(200, {"success": True, "message": message})
                except Exception as exc:  # noqa: BLE001
                    self._json(500, {"success": False, "error": str(exc)})
            finally:
                busy.release()

        def log_message(self, fmt: str, *args) -> None:
            pass

    return Handler


def serve(web_root: Path | None = None, *, require_access=False) -> None:
    access_config = load_access_config(required=require_access)
    root = (web_root or Path(__file__).resolve().parent.parent / "web" / "dist").resolve()
    index = root / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"Built slicer UI not found at {root}; build the web UI first so web/dist/index.html exists.")
    if index.read_text(encoding="utf-8").count(TOKEN_PLACEHOLDER) != 1:
        raise RuntimeError(f"{index} must contain exactly one {TOKEN_PLACEHOLDER} placeholder")
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((HOST, PORT), make_handler(root, token, access_config=access_config))
    if access_config:
        url = access_config["public_origin"]
        print(f"Three_Slicer public UI: {url}", flush=True)
    else:
        url = f"http://{HOST}:{server.server_port}/"
        print(f"Three_Slicer local UI: {url}", flush=True)
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
