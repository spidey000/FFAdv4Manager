"""Regression checks for the local printer manager bridge; no physical printer needed."""
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from server import ad4_bridge as bridge


class BridgeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bridge.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=4)

    def request(self, route, obj=None, origin=None):
        url = 'http://127.0.0.1:' + str(self.port) + route
        headers = {'Origin': origin or 'http://127.0.0.1:' + str(self.port)}
        if obj is None:
            req = Request(url, headers=headers)
        else:
            headers['Content-Type'] = 'application/json'
            req = Request(url, data=json.dumps(obj).encode(), headers=headers)
        with urlopen(req, timeout=4) as response:
            return json.load(response)

    def test_safe_names_and_private_host(self):
        self.assertEqual(bridge.safe_filename('model.gcode'), 'model.gcode')
        with self.assertRaises(ValueError):
            bridge.safe_filename('../evil.gx')
        with self.assertRaises(ValueError):
            bridge.safe_filename('evil.exe')
        self.assertTrue(bridge.private_ip('192.168.1.5'))
        self.assertFalse(bridge.private_ip('8.8.8.8'))
        self.assertFalse(bridge.private_ip('127.0.0.1'))

    def test_session_endpoint_and_reject_cross_origin(self):
        self.assertIn('notifying', self.request('/api/printer/session'))
        with self.assertRaises(HTTPError) as ctx:
            self.request('/api/printer/actions', {'action': 'pause'}, 'https://untrusted.example')
        self.assertEqual(ctx.exception.code, 403)

    def test_status_and_whitelisted_action(self):
        def cmd(*args, **kwargs):
            if args == ('status', '--json'):
                return '{"machine_status":"READY","bed_current":25}'
            if args == ('pause',):
                return 'ok'
            raise AssertionError('unexpected command ' + repr(args))
        with patch.object(bridge, 'command', side_effect=cmd):
            self.assertEqual(self.request('/api/printer/status')['machine_status'], 'READY')
            self.assertEqual(self.request('/api/printer/actions', {'action': 'pause'}), {'detail': 'ok'})
        with self.assertRaises(HTTPError) as ctx:
            self.request('/api/printer/actions', {'action': 'home'})
        self.assertEqual(ctx.exception.code, 502)

    def test_remote_print_requires_listed_filename(self):
        def cmd(*args, **kwargs):
            if args == ('files', '--json'):
                return '["/data/good.gx"]'
            if args == ('print', '/data/good.gx'):
                return 'started'
            raise AssertionError(args)
        with patch.object(bridge, 'command', side_effect=cmd):
            self.assertEqual(self.request('/api/printer/actions',
                              {'action': 'print', 'file': '/data/good.gx'})['detail'], 'started')
            with self.assertRaises(HTTPError):
                self.request('/api/printer/actions',
                             {'action': 'print', 'file': '/data/other.gx'})

    def test_discovery_and_selection(self):
        with patch.object(bridge, 'command', return_value='[{"name":"AD4","ip":"192.168.1.42","port":8899}]'):
            devices = self.request('/api/printer/discover')
        self.assertEqual(len(devices), 1)
        selection = self.request('/api/printer/selection', {'host': '192.168.1.42'})
        self.assertEqual(selection['host'], '192.168.1.42')
        self.assertIn('--host', bridge.cli_argv('status'))
        with self.assertRaises(HTTPError):
            self.request('/api/printer/selection', {'host': '192.168.1.99'})


if __name__ == '__main__':
    unittest.main()
