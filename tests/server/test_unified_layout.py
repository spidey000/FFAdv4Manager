"""Static integration contracts that require no printer."""
from pathlib import Path
import unittest
from server import ad4_bridge


class UnifiedLayoutChecks(unittest.TestCase):
    def test_dist_location_and_url_root(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(ad4_bridge.DIST, root / "frontend" / "dist")
        self.assertEqual(ad4_bridge.BASE, "/")

    def test_server_bind_is_loopback_only(self):
        import inspect
        code = inspect.getsource(ad4_bridge.serve)
        self.assertIn("('127.0.0.1', port)", code)
        self.assertIn("require_access and not ACCESS_CONFIG", code)


if __name__ == "__main__":
    unittest.main()
