"""Optional fail-closed Cloudflare Access validation for the ThreeSlicer origin.

No Cloudflare configuration: local-loopback mode stays supported.
All four CF_ACCESS_* settings present: the HTTP origin accepts ONLY the
configured public Host with a valid, signed, audience-scoped Access JWT.
"""
import re
from functools import lru_cache
from urllib.parse import urlsplit


_REQUIRED = ('CF_ACCESS_TEAM_DOMAIN', 'CF_ACCESS_AUD',
             'CF_ACCESS_PUBLIC_ORIGIN', 'CF_ACCESS_EMAIL')


def load_access_config(environ):
    settings = {key: environ.get(key, '').strip() for key in _REQUIRED}
    if not any(settings.values()):
        return None
    if not all(settings.values()):
        raise ValueError('Cloudflare Access requires all four settings: ' + ', '.join(_REQUIRED))

    domain = settings['CF_ACCESS_TEAM_DOMAIN'].lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.cloudflareaccess\.com', domain):
        raise ValueError('CF_ACCESS_TEAM_DOMAIN must be a team hostname ending in .cloudflareaccess.com')
    public = settings['CF_ACCESS_PUBLIC_ORIGIN']
    parsed = urlsplit(public)
    if (parsed.scheme != 'https' or not parsed.hostname
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.path or parsed.query or parsed.fragment
            or parsed.netloc != parsed.hostname):
        raise ValueError('CF_ACCESS_PUBLIC_ORIGIN must be an exact https://hostname origin')
    email = settings['CF_ACCESS_EMAIL'].lower()
    if (not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)
            or not settings['CF_ACCESS_AUD']):
        raise ValueError('A valid Access user email and application AUD are required')

    return {
        'issuer': 'https://' + domain,
        'jwks_url': 'https://' + domain + '/cdn-cgi/access/certs',
        'audience': settings['CF_ACCESS_AUD'],
        'public_origin': public,
        'public_host': parsed.hostname,
        'email': email,
    }


@lru_cache(maxsize=2)
def _jwks_client(jwks_url):
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError('Install PyJWT[crypto] for Cloudflare Access validation') from exc
    return jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300,
                           cache_keys=True, timeout=6)


def verify_access_jwt(token, config):
    """Reject tokens with invalid signature, issuer, AUD, expiration or email."""
    if not isinstance(token, str) or len(token) < 20 or len(token) > 16000:
        return False
    try:
        import jwt
        signing_key = _jwks_client(config['jwks_url']).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=['RS256'], issuer=config['issuer'],
            audience=config['audience'], options={'require': ['exp', 'iss', 'aud']},
            leeway=30,
        )
        return isinstance(claims.get('email'), str) and (
            claims['email'].lower() == config['email'])
    except Exception:
        # No JWT, invalid JWT or unavailable Cloudflare JWKS => fail closed.
        return False
