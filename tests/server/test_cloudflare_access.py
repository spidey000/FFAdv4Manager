"""Security regression tests. Uses generated test-only JWT keys; no printer calls."""
import json
import threading
import time
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import ad4_bridge as bridge
from server import cloudflare_access as access


TEST_ENV = {
    'CF_ACCESS_TEAM_DOMAIN': 'test-team.cloudflareaccess.com',
    'CF_ACCESS_AUD': 'unit-test-audience',
    'CF_ACCESS_PUBLIC_ORIGIN': 'https://slicer.example.com',
    'CF_ACCESS_EMAIL': 'operator@example.com',
}


class AccessConfigurationTests(unittest.TestCase):
    def test_disabled_and_incomplete(self):
        self.assertIsNone(access.load_access_config({}))
        with self.assertRaises(ValueError):
            access.load_access_config({'CF_ACCESS_AUD': 'abc'})

    def test_valid_and_malformed_origin(self):
        config = access.load_access_config(TEST_ENV)
        self.assertEqual(config['public_host'], 'slicer.example.com')
        self.assertEqual(config['issuer'], 'https://test-team.cloudflareaccess.com')
        for public in ('http://slicer.example.com',
                       'https://slicer.example.com/evil',
                       'https://attacker@slicer.example.com',
                       'https://slicer.example.com:8443'):
            with self.subTest(public=public), self.assertRaises(ValueError):
                access.load_access_config({**TEST_ENV, 'CF_ACCESS_PUBLIC_ORIGIN': public})

    def test_real_signature_issuer_audience_email_and_expiry(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        config = access.load_access_config(TEST_ENV)
        from types import SimpleNamespace
        with patch.object(access, '_jwks_client', return_value=SimpleNamespace(
                get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key()))):
            claims = {'iss': config['issuer'], 'aud': [config['audience']],
                      'email': config['email'], 'exp': int(time.time()) + 300}
            def signed(**kwargs):
                return jwt.encode({**claims, **kwargs}, private, algorithm='RS256')
            self.assertTrue(access.verify_access_jwt(signed(), config))
            self.assertFalse(access.verify_access_jwt(signed(email='other@example.com'), config))
            self.assertFalse(access.verify_access_jwt(signed(aud=['wrong-app']), config))
            self.assertFalse(access.verify_access_jwt(signed(iss='https://evil.example'), config))
            self.assertFalse(access.verify_access_jwt(signed(exp=int(time.time()) - 3600), config))
            self.assertFalse(access.verify_access_jwt('not-a-jwt', config))
            other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            malicious = jwt.encode(claims, other, algorithm='RS256')
            self.assertFalse(access.verify_access_jwt(malicious, config))


class ProtectedBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), bridge.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)

    def request(self, path, *, host='slicer.example.com', origin=None, token=None, data=None):
        headers = {'Host': host}
        if origin is not None:
            headers['Origin'] = origin
        if token is not None:
            headers['Cf-Access-Jwt-Assertion'] = token
        if data is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(data).encode()
        req = Request('http://127.0.0.1:' + str(self.port) + path, data=data, headers=headers)
        with urlopen(req, timeout=3) as response:
            return json.load(response)

    def test_no_public_or_local_bypass_in_protected_mode(self):
        with patch.object(bridge, 'ACCESS_CONFIG', access.load_access_config(TEST_ENV)):
            for kwargs in ({}, {'host': '127.0.0.1:' + str(self.port)},
                           {'token': 'bad-token'}):
                with self.subTest(kwargs=kwargs), self.assertRaises(HTTPError) as err:
                    self.request('/api/printer/session', **kwargs)
                self.assertEqual(err.exception.code, 401)
            with patch.object(bridge, 'verify_access_jwt', return_value=True) as verify:
                result = self.request('/api/printer/session', token='test-jwt')
                self.assertIn('notifying', result)
                verify.assert_called()
                with self.assertRaises(HTTPError) as err:
                    self.request('/api/printer/actions', token='test-jwt',
                                 origin='https://attacker.example', data={'action': 'pause'})
                self.assertEqual(err.exception.code, 401)
                with self.assertRaises(HTTPError) as err:
                    self.request('/api/printer/actions', token='test-jwt',
                                 data={'action': 'pause'})
                self.assertEqual(err.exception.code, 401)
                with patch.object(bridge, 'command', return_value='ok') as command:
                    result = self.request('/api/printer/actions', token='test-jwt',
                                          origin=TEST_ENV['CF_ACCESS_PUBLIC_ORIGIN'],
                                          data={'action': 'pause'})
                    self.assertEqual(result['detail'], 'ok')
                    command.assert_called_once_with('pause', timeout=50)


if __name__ == '__main__':
    unittest.main()
