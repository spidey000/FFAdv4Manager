"""Hardware-free integration tests for the consolidated repository."""
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch
from urllib.request import Request, urlopen
import json
import unittest

from server import ad4_bridge as bridge


class UnifiedLayoutChecks(unittest.TestCase):
    def test_dist_location_and_url_root(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(bridge.DIST, root / "frontend" / "dist")
        self.assertEqual(bridge.BASE, "/")

    def test_server_bind_is_loopback_only(self):
        import inspect
        code = inspect.getsource(bridge.serve)
        self.assertIn("('127.0.0.1', port)", code)
        self.assertIn("require_access and not ACCESS_CONFIG", code)

    def test_root_and_assets_are_served_and_api_remains_separate(self):
        with TemporaryDirectory() as temp, patch.object(bridge, "DIST", Path(temp)):
            folder = Path(temp)
            (folder / "index.html").write_text("<html>Integrated UI</html>", encoding="utf-8")
            (folder / "assets").mkdir()
            (folder / "assets" / "app.js").write_text("window.integrated = true;", encoding="utf-8")
            server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.Handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                origin = "http://127.0.0.1:" + str(server.server_address[1])
                with urlopen(origin + "/", timeout=3) as r:
                    self.assertIn("Integrated UI", r.read().decode())
                with urlopen(origin + "/assets/app.js", timeout=3) as r:
                    self.assertIn("window.integrated", r.read().decode())
                with patch.object(bridge, "command", return_value='{"machine_status":"READY"}'):
                    with urlopen(origin + "/api/printer/status", timeout=3) as r:
                        self.assertEqual(json.load(r)["machine_status"], "READY")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
