"""Regression checks for the local printer manager bridge; no physical printer needed."""
import json
from pathlib import Path
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


    def test_slicer_upload_keeps_model_name_and_reports_real_gx_name(self):
        calls = []

        def fake_cli(*args, **kwargs):
            self.assertEqual(args[0], 'upload')
            temp = Path(args[1])
            calls.append((temp.name, temp.read_bytes()))
            return 'uploaded\\nUploaded and listed: 0:/user/01_02_1.23m_Benchy.gx\\n'

        url = 'http://127.0.0.1:' + str(self.port) + '/api/printer/jobs?start=false&name=Benchy.gcode'
        headers = {'Origin': 'http://127.0.0.1:' + str(self.port),
                   'Content-Type': 'text/plain; charset=utf-8'}
        with patch.object(bridge, 'command', side_effect=fake_cli):
            request = Request(url, data=b'G28\\nG1 X10\\n', headers=headers, method='POST')
            with urlopen(request, timeout=4) as response:
                result = json.load(response)
        self.assertEqual(calls, [('Benchy.gcode', b'G28\\nG1 X10\\n')])
        self.assertEqual(result['remote_name'], '01_02_1.23m_Benchy.gx')
        self.assertEqual(result['remote_path'], '0:/user/01_02_1.23m_Benchy.gx')
        self.assertFalse(result['started'])

    def test_uploaded_gx_filename_is_preserved_and_missing_job_name_rejected(self):
        def fake_cli(*args, **kwargs):
            self.assertEqual(Path(args[1]).name, 'my-part.gx')
            return 'Uploaded and listed: 0:/user/00_33_0.54m_my-part.gx\\n'

        base = 'http://127.0.0.1:' + str(self.port)
        headers = {'Origin': base, 'Content-Type': 'application/octet-stream'}
        with patch.object(bridge, 'command', side_effect=fake_cli):
            req = Request(base + '/api/printer/upload?name=my-part.gx',
                          data=b'xgcode 1.0\\n\\0', headers=headers, method='POST')
            with urlopen(req, timeout=4) as response:
                self.assertEqual(json.load(response)['remote_name'], '00_33_0.54m_my-part.gx')
        req = Request(base + '/api/printer/jobs?start=false', data=b'G28\\n',
                      headers={'Origin': base, 'Content-Type': 'text/plain'}, method='POST')
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=4)
        self.assertEqual(ctx.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
