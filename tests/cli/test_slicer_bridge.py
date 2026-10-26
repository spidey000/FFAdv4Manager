from pathlib import Path
from http.server import ThreadingHTTPServer
import http.client
import json
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from ffadv4manager import slicer_bridge


@pytest.mark.parametrize("name", ["../part.gcode", "..\\part.gcode", "/tmp/part.gcode", "part.gcode;id", "part.gx", ""])
def test_remote_name_rejects_paths_and_unsafe_names(name):
    with pytest.raises(ValueError):
        slicer_bridge.safe_remote_name(name)


def test_remote_name_accepts_plain_gcode_basename():
    assert slicer_bridge.safe_remote_name("My_part-01.GCODE") == "My_part-01.GCODE"


def test_request_schema_is_strict():
    valid = b'{"filename":"safe.gcode","gcode":"G1 X1","start":false}'
    assert slicer_bridge.validate_print_request(valid) == ("safe.gcode", "G1 X1", False)
    for invalid in (
        b'{"filename":"safe.gcode","gcode":"G1","start":0}',
        b'{"filename":"safe.gcode","gcode":"G1","start":false,"extra":1}',
        b'{"filename":"safe.gcode","gcode":"G1","start":false,"start":true}',
    ):
        with pytest.raises((ValueError, TypeError)):
            slicer_bridge.validate_print_request(invalid)


@pytest.mark.parametrize("start", [False, True])
def test_upload_uses_fixed_module_argv_and_cleans_temp_file(monkeypatch, start):
    captured = {}

    def fake_run(argv, **kwargs):
        captured.update(argv=argv, kwargs=kwargs)
        captured["content"] = Path(argv[4]).read_text()
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    monkeypatch.setattr(slicer_bridge.subprocess, "run", fake_run)
    result = slicer_bridge.invoke_upload("G1 X1\n", "safe.gcode", start)
    argv = captured["argv"]
    assert result.returncode == 0
    assert argv[:3] == [slicer_bridge.sys.executable, "-m", "ffadv4manager.cli"]
    assert argv[3] == "upload"
    assert Path(argv[4]).suffix == ".gcode"
    assert argv[5:] == ["--remote-name", "safe.gcode"] + (["--start"] if start else [])
    assert captured["content"] == "G1 X1\n"
    assert captured["kwargs"] == {"capture_output": True, "text": True, "check": False}
    assert not Path(argv[4]).exists()


def test_camera_snapshot_cli_uses_fixed_argv_timeout_and_cleans_output(monkeypatch):
    captured = {}
    jpeg = b"\xff\xd8frame\xff\xd9"

    def fake_run(argv, **kwargs):
        captured.update(argv=argv, kwargs=kwargs)
        Path(argv[-1]).write_bytes(jpeg)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(slicer_bridge.subprocess, "run", fake_run)
    assert slicer_bridge.invoke_camera_snapshot() == jpeg
    assert captured["argv"][:5] == [slicer_bridge.sys.executable, "-m", "ffadv4manager.cli", "camera", "snapshot"]
    assert Path(captured["argv"][-1]).suffix == ".jpg"
    assert captured["kwargs"] == {
        "capture_output": True, "text": True, "check": False,
        "timeout": slicer_bridge.CAMERA_SNAPSHOT_TIMEOUT,
    }
    assert not Path(captured["argv"][-1]).exists()


def test_slicer_server_defaults_to_loopback_and_web_dist(tmp_path, monkeypatch):
    index = tmp_path / "index.html"
    index.write_text(f"<script>{slicer_bridge.TOKEN_PLACEHOLDER}</script>")
    seen = {}

    class FakeServer:
        server_port = 45678

        def __init__(self, address, handler):
            seen.update(address=address, handler=handler)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            seen["closed"] = True

    monkeypatch.setattr(slicer_bridge, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(slicer_bridge.webbrowser, "open", lambda url: seen.update(url=url))
    monkeypatch.setattr(slicer_bridge, "load_access_config", lambda required=False: None)
    slicer_bridge.serve(tmp_path)
    assert seen["address"] == ("127.0.0.1", slicer_bridge.PORT)
    assert seen["url"] == "http://127.0.0.1:45678/"
    assert seen["closed"] is True


def test_slicer_server_access_mode_reports_public_url_without_opening_browser(tmp_path, monkeypatch, capsys):
    index = tmp_path / "index.html"
    index.write_text(f"<script>{slicer_bridge.TOKEN_PLACEHOLDER}</script>")
    seen = {}
    config = {"public_origin": "https://print.example.com", "jwks_url": "https://team.example.com/certs"}

    class FakeServer:
        server_port = 45678

        def __init__(self, address, handler):
            seen.update(address=address, handler=handler)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            seen["closed"] = True

    monkeypatch.setattr(slicer_bridge, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(slicer_bridge, "load_access_config", lambda required=False: config)
    monkeypatch.setattr(slicer_bridge.webbrowser, "open", lambda url: seen.update(opened=url))
    slicer_bridge.serve(tmp_path)
    assert seen["address"] == ("127.0.0.1", slicer_bridge.PORT)
    assert "opened" not in seen
    assert "Three_Slicer public UI: https://print.example.com" in capsys.readouterr().out
    assert seen["closed"] is True


def test_missing_ui_build_has_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="build the web UI first"):
        slicer_bridge.serve(tmp_path)


@pytest.fixture
def http_bridge(tmp_path, access_config=None):
    calls = []
    snapshots = []

    def upload(gcode, remote_name, start):
        calls.append((gcode, remote_name, start))
        return subprocess.CompletedProcess([], 0, "ok", "")

    def snapshot():
        snapshots.append(True)
        return b"\xff\xd8first-frame\xff\xd9"

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        slicer_bridge.make_handler(tmp_path, "test-secret-token", upload, access_config=access_config, snapshot=snapshot),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, calls, snapshots
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def post_print(port, *, origin="correct", host="correct", token="correct", assertion=None, content_type="application/json", payload=None):
    authority = f"127.0.0.1:{port}"
    headers = {"Content-Type": content_type, "Authorization": "Bearer test-secret-token"}
    if assertion is not None:
        headers["Cf-Access-Jwt-Assertion"] = assertion
    if origin == "correct":
        headers["Origin"] = f"http://{authority}"
    elif origin == "wrong":
        headers["Origin"] = "http://example.com"
    elif origin == "public":
        headers["Origin"] = "https://print.example.com"
    if host == "correct":
        headers["Host"] = authority
    elif host == "wrong":
        headers["Host"] = "example.com"
    elif host == "missing":
        # http.client otherwise supplies its own Host header automatically.
        headers["Host"] = ""
    elif host == "public":
        headers["Host"] = "print.example.com"
    if token == "missing":
        headers.pop("Authorization")
    elif token == "wrong":
        headers["Authorization"] = "Bearer wrong-token"
    body = payload if payload is not None else b'{"filename":"safe.gcode","gcode":"G1 X1","start":false}'
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    connection.request("POST", "/api/print", body=body, headers=headers)
    response = connection.getresponse()
    result = response.status, response.read()
    connection.close()
    return result


def post_snapshot(port, *, origin="correct", host="correct", token="correct", assertion=None, body=b""):
    authority = f"127.0.0.1:{port}"
    headers = {"Authorization": "Bearer test-secret-token", "Host": authority}
    if origin == "correct":
        headers["Origin"] = f"http://{authority}"
    elif origin == "wrong":
        headers["Origin"] = "http://example.com"
    elif origin == "public":
        headers["Origin"] = "https://print.example.com"
    if host == "wrong":
        headers["Host"] = "example.com"
    elif host == "missing":
        headers["Host"] = ""
    elif host == "public":
        headers["Host"] = "print.example.com"
    if token == "missing":
        headers.pop("Authorization")
    elif token == "wrong":
        headers["Authorization"] = "Bearer wrong-token"
    if assertion is not None:
        headers["Cf-Access-Jwt-Assertion"] = assertion
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    connection.request("POST", "/api/camera/snapshot", body=body, headers=headers)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


@pytest.mark.parametrize(
    "kwargs,expected_status",
    [
        ({"origin": "wrong"}, 403),
        ({"origin": "missing"}, 403),
        ({"host": "wrong"}, 403),
        ({"host": "missing"}, 403),
        ({"token": "wrong"}, 401),
        ({"token": "missing"}, 401),
        ({"content_type": "text/plain"}, 415),
    ],
)
def test_http_rejects_unauthorized_requests_without_upload(http_bridge, kwargs, expected_status):
    port, calls, _ = http_bridge
    status, body = post_print(port, **kwargs)
    assert status == expected_status
    assert json.loads(body)["success"] is False
    assert calls == []


def test_http_valid_upload_only_succeeds_without_start(http_bridge):
    port, calls, _ = http_bridge
    status, body = post_print(port)
    assert status == 200
    result = json.loads(body)
    assert result["success"] is True
    assert result["message"] == "Upload completed"
    assert calls == [("G1 X1", "safe.gcode", False)]


def test_http_explicit_start_true_passes_start_to_mock_upload(http_bridge):
    port, calls, _ = http_bridge
    status, body = post_print(port, payload=b'{"filename":"safe.gcode","gcode":"G1 X1","start":true}')
    assert status == 200
    result = json.loads(body)
    assert result["success"] is True
    assert result["message"] == "Upload completed; print-start command acknowledged; physical printing not verified"
    assert calls == [("G1 X1", "safe.gcode", True)]


def test_camera_snapshot_returns_jpeg_with_security_and_cache_headers(http_bridge):
    port, calls, snapshots = http_bridge
    status, headers, body = post_snapshot(port)
    assert status == 200
    assert body == b"\xff\xd8first-frame\xff\xd9"
    assert headers["Content-Type"] == "image/jpeg"
    assert headers["Content-Length"] == str(len(body))
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert snapshots == [True]
    assert calls == []


@pytest.mark.parametrize(
    "kwargs,expected_status",
    [
        ({"origin": "wrong"}, 403), ({"origin": "missing"}, 403),
        ({"host": "wrong"}, 403), ({"host": "missing"}, 403),
        ({"token": "wrong"}, 401), ({"token": "missing"}, 401),
        ({"body": b"not empty"}, 400),
    ],
)
def test_camera_snapshot_rejects_unauthorized_or_nonempty_requests(http_bridge, kwargs, expected_status):
    port, _, snapshots = http_bridge
    status, _, body = post_snapshot(port, **kwargs)
    assert status == expected_status
    assert json.loads(body)["success"] is False
    assert snapshots == []


def test_camera_snapshot_failure_is_bounded_json_without_cli_details(tmp_path):
    secret = "private-camera-url"

    def failed_snapshot():
        raise RuntimeError(secret)

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        slicer_bridge.make_handler(tmp_path, "test-secret-token", snapshot=failed_snapshot),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, headers, body = post_snapshot(server.server_port)
        assert status == 502
        assert headers["Content-Type"].startswith("application/json")
        payload = json.loads(body)
        assert payload == {"success": False, "error": "Camera snapshot failed"}
        assert secret not in body.decode()
        assert headers["Content-Length"] == str(len(body))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_access_assertion_required_and_verified_before_upload(monkeypatch):
    config = {
        "issuer": "https://team.example.com", "jwks_url": "https://team.example.com/cdn-cgi/access/certs",
        "audience": "fixed-audience", "email": "allowed@example.com",
        "public_origin": "https://print.example.com", "public_host": "print.example.com",
    }
    calls = []
    def upload(gcode, remote_name, start):
        calls.append((gcode, remote_name, start))
        return subprocess.CompletedProcess([], 0, "ok", "")
    monkeypatch.setattr(slicer_bridge.jwt, "PyJWKClient", lambda *args, **kwargs: object())
    server = ThreadingHTTPServer(("127.0.0.1", 0), slicer_bridge.make_handler(Path("."), "test-secret-token", upload, access_config=config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_port
    try:
        outcomes = {"good": True, "bad": False, "wrong-email": False}
        seen = []
        def verify(assertion, actual_config, jwks_client):
            seen.append((assertion, actual_config))
            return outcomes.get(assertion, False)
        monkeypatch.setattr(slicer_bridge, "verify_access_assertion", verify)
        assert post_print(port)[0] == 401
        assert post_print(port, assertion="bad")[0] == 401
        assert post_print(port, assertion="wrong-email")[0] == 401
        assert calls == []
        assert post_print(port, assertion="good")[0] == 200
        assert calls == [("G1 X1", "safe.gcode", False)]
        assert [item[0] for item in seen] == ["bad", "wrong-email", "good"]
        assert all(item[1] is config for item in seen)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_camera_snapshot_requires_access_assertion_when_configured(monkeypatch):
    config = {
        "issuer": "https://team.example.com", "jwks_url": "https://team.example.com/certs",
        "audience": "fixed-audience", "email": "allowed@example.com",
        "public_origin": "https://print.example.com", "public_host": "print.example.com",
    }
    snapshots = []
    monkeypatch.setattr(slicer_bridge.jwt, "PyJWKClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(slicer_bridge, "verify_access_assertion", lambda assertion, *_: assertion == "good")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        slicer_bridge.make_handler(Path("."), "test-secret-token", access_config=config,
                                   snapshot=lambda: snapshots.append(True) or b"\xff\xd8x\xff\xd9"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        assert post_snapshot(port, host="public", origin="public")[0] == 401
        assert post_snapshot(port, host="public", origin="public", assertion="bad")[0] == 401
        assert snapshots == []
        status, _, _ = post_snapshot(port, host="public", origin="public", assertion="good")
        assert status == 200
        assert snapshots == [True]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_access_configuration_is_all_or_nothing():
    with pytest.raises(RuntimeError, match="must set all"):
        slicer_bridge.load_access_config({"CF_ACCESS_TEAM_DOMAIN": "team.example.com"})
    assert slicer_bridge.load_access_config({}) is None
    with pytest.raises(RuntimeError, match="Cloudflare Access is required"):
        slicer_bridge.load_access_config({}, required=True)


def test_access_configuration_loads_optional_service_token_id():
    environ = {
        "CF_ACCESS_TEAM_DOMAIN": "team.example.com",
        "CF_ACCESS_AUD": "fixed-audience",
        "CF_ACCESS_EMAIL": "allowed@example.com",
        "CF_ACCESS_PUBLIC_ORIGIN": "https://print.example.com",
        "CF_ACCESS_SERVICE_TOKEN_ID": "bot-client-id",
    }
    config = slicer_bridge.load_access_config(environ)
    assert config["service_token_id"] == "bot-client-id"
    del environ["CF_ACCESS_SERVICE_TOKEN_ID"]
    assert slicer_bridge.load_access_config(environ)["service_token_id"] == ""


def test_require_access_prevents_startup_without_configuration(tmp_path, monkeypatch):
    index = tmp_path / "index.html"
    index.write_text(f"<script>{slicer_bridge.TOKEN_PLACEHOLDER}</script>")
    load_access_config = slicer_bridge.load_access_config
    monkeypatch.setattr(slicer_bridge, "load_access_config", lambda required=False: load_access_config({}, required=required))
    with pytest.raises(RuntimeError, match="Cloudflare Access is required"):
        slicer_bridge.serve(tmp_path, require_access=True)


@pytest.fixture
def generated_access_key(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    class LocalJwksClient:
        instances = []
        def __init__(self, url, **kwargs):
            self.url, self.kwargs = url, kwargs
            self.calls = 0
            self.instances.append(self)
        def get_signing_key_from_jwt(self, assertion):
            self.calls += 1
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr(slicer_bridge.jwt, "PyJWKClient", LocalJwksClient)
    config = {
        "issuer": "https://team.example.com", "jwks_url": "https://team.example.com/cdn-cgi/access/certs",
        "audience": "fixed-audience", "email": "allowed@example.com",
        "service_token_id": "bot-client-id",
        "public_origin": "https://print.example.com", "public_host": "print.example.com",
    }

    def token(**overrides):
        claims = {"iss": config["issuer"], "aud": config["audience"], "exp": int(time.time()) + 300,
                  "email": config["email"]}
        claims.update(overrides)
        return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "local-key"})

    return config, private_key, token, LocalJwksClient


def _get(port, host, *, origin=None, assertion=None, path="/"):
    headers = {"Host": host}
    if origin is not None:
        headers["Origin"] = origin
    if assertion is not None:
        headers["Cf-Access-Jwt-Assertion"] = assertion
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    connection.request("GET", path, headers=headers)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def test_public_get_requires_access_assertion_with_optional_exact_origin(tmp_path, generated_access_key):
    config, _, token, _ = generated_access_key
    (tmp_path / "index.html").write_text(f"<script>{slicer_bridge.TOKEN_PLACEHOLDER}</script>")
    (tmp_path / "asset.js").write_text("ok")
    server = ThreadingHTTPServer(("127.0.0.1", 0), slicer_bridge.make_handler(tmp_path, "ephemeral-token", access_config=config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        assert _get(port, config["public_host"])[0] == 401
        assert _get(port, config["public_host"], assertion=token(), origin="https://wrong.example")[0] == 403
        status, headers, body = _get(port, config["public_host"], assertion=token())
        assert status == 200 and b"ephemeral-token" in body
        assert headers["Cache-Control"] == "no-store"
        assert _get(port, config["public_host"], assertion=token(), origin=config["public_origin"], path="/asset.js")[0] == 200
        assert _get(port, "evil.example", assertion=token())[0] == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("kind", ["expired", "issuer", "audience", "signature", "email"])
def test_crypto_assertion_failures_never_call_upload_or_start(tmp_path, generated_access_key, kind):
    config, private_key, token, _ = generated_access_key
    calls = []
    def upload(*args):
        calls.append(args)
        return subprocess.CompletedProcess([], 0, "ok", "")
    server = ThreadingHTTPServer(("127.0.0.1", 0), slicer_bridge.make_handler(tmp_path, "test-secret-token", upload, access_config=config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if kind == "expired":
            assertion = token(exp=int(time.time()) - 10)
        elif kind == "issuer":
            assertion = token(iss="https://wrong.example")
        elif kind == "audience":
            assertion = token(aud="wrong-audience")
        elif kind == "signature":
            other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            assertion = jwt.encode({"iss": config["issuer"], "aud": config["audience"], "exp": int(time.time()) + 300,
                                   "email": config["email"]}, other_key, algorithm="RS256", headers={"kid": "other"})
        else:
            assertion = token(email="other@example.com")
        status, _ = post_print(server.server_port, assertion=assertion,
                               payload=b'{"filename":"safe.gcode","gcode":"G1 X1","start":true}')
        assert status == 401
        assert calls == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize(
    "service_token_id,claims,expected",
    [
        ("bot-client-id", {"email": "allowed@example.com"}, True),
        ("bot-client-id", {"email": "other@example.com", "common_name": "bot-client-id"}, True),
        ("bot-client-id", {"email": "other@example.com", "common_name": "different-client-id"}, False),
        ("", {"email": "other@example.com", "common_name": "bot-client-id"}, False),
    ],
)
def test_access_assertion_accepts_only_allowed_human_or_configured_bot(
    generated_access_key, service_token_id, claims, expected
):
    config, _, token, client_class = generated_access_key
    config["service_token_id"] = service_token_id
    assertion = token(**claims)
    assert slicer_bridge.verify_access_assertion(assertion, config, client_class(config["jwks_url"])) is expected


def test_access_assertion_accepts_service_token_without_email(generated_access_key):
    config, private_key, _, client_class = generated_access_key
    config["service_token_id"] = "bot-client-id"
    claims = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": int(time.time()) + 300,
        "common_name": "bot-client-id",
    }
    assertion = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "local-key"})
    assert slicer_bridge.verify_access_assertion(
        assertion, config, client_class(config["jwks_url"])
    ) is True


def test_access_upload_start_uses_cached_jwks_client_test_double(tmp_path, generated_access_key):
    config, _, token, client_class = generated_access_key
    calls = []
    def upload(*args):
        calls.append(args)
        return subprocess.CompletedProcess([], 0, "ok", "")
    server = ThreadingHTTPServer(("127.0.0.1", 0), slicer_bridge.make_handler(tmp_path, "test-secret-token", upload, access_config=config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _ = post_print(server.server_port, host="public", origin="wrong", assertion=token(),
                               payload=b'{"filename":"safe.gcode","gcode":"G1 X1","start":true}')
        assert status == 403 and calls == []
        status, _ = post_print(server.server_port, host="public", origin="public", assertion=token(),
                               payload=b'{"filename":"safe.gcode","gcode":"G1 X1","start":true}')
        assert status == 200
        assert calls == [("G1 X1", "safe.gcode", True)]
        assert len(client_class.instances) == 1
        client = client_class.instances[0]
        assert client.kwargs == {
            "cache_jwk_set": True, "cache_keys": True, "lifespan": 300,
            "timeout": 5, "max_cached_keys": 16,
        }
        assert client.calls == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_http_accepts_gcode_larger_than_previous_limit(http_bridge):
    port, calls, _ = http_bridge
    gcode = "G" * (8 * 1024 * 1024 + 128 * 1024)
    payload = json.dumps({"filename": "large.gcode", "gcode": gcode, "start": False}).encode()
    status, body = post_print(port, payload=payload)
    assert status == 200
    assert json.loads(body)["success"] is True
    assert len(calls) == 1
    assert calls[0] == (gcode, "large.gcode", False)


def test_http_body_timeout_rejects_request_and_releases_upload_lock(http_bridge, monkeypatch):
    monkeypatch.setattr(slicer_bridge, "BODY_READ_TIMEOUT", 0.05)
    port, calls, _ = http_bridge
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    connection.putrequest("POST", "/api/print")
    connection.putheader("Host", f"127.0.0.1:{port}")
    connection.putheader("Origin", f"http://127.0.0.1:{port}")
    connection.putheader("Authorization", "Bearer test-secret-token")
    connection.putheader("Content-Type", "application/json")
    connection.putheader("Content-Length", "100")
    connection.endheaders()
    connection.send(b'{"filename":"safe.gcode"')
    response = connection.getresponse()
    assert response.status == 408
    assert json.loads(response.read())["success"] is False
    connection.close()
    assert calls == []

    status, body = post_print(port)
    assert status == 200
    assert json.loads(body)["success"] is True
    assert calls == [("G1 X1", "safe.gcode", False)]
