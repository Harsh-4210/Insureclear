"""Auth routes are exercised independently of workers and provider calls."""
import importlib
import importlib.util

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

PASSWORD = 'synthetic passphrase 19'
ORIGIN = 'https://pilot.example.test'


@pytest.fixture
def auth(monkeypatch, tmp_path):
    assert importlib.util.find_spec('web.auth') is not None, 'Account routes are missing'
    module = importlib.import_module('web.auth')
    from tools.auth_store import AuthStore
    store = AuthStore(tmp_path / 'auth.sqlite3')
    store.create_user('alice', PASSWORD, 'org-a', 'claimant')
    monkeypatch.setattr(module, 'get_store', lambda: store)
    monkeypatch.setenv('INSURECLEAR_AUTH_MODE', 'accounts')
    monkeypatch.setenv('INSURECLEAR_CORS_ORIGINS', ORIGIN)
    monkeypatch.delenv('INSURECLEAR_AUTH_COOKIE_SECURE', raising=False)
    app = FastAPI()
    app.include_router(module.router)
    @app.post('/mutation')
    def mutation(request: Request, principal=Depends(module.current_principal)):
        module.require_mutation(request, principal)
        return {'user_id': principal['user_id']}
    return module, store, TestClient(app, base_url=ORIGIN)


def login(client):
    return client.post('/api/auth/login', headers={'Origin': ORIGIN}, json={'username': 'alice', 'password': PASSWORD})


def test_session_cookie_and_public_response(auth):
    _, _, client = auth
    response = login(client)
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
    assert 'Max-Age=28800' in cookie
    assert response.headers['cache-control'] == 'no-store'
    session = client.get('/api/auth/session')
    assert session.status_code == 200
    assert session.json()['user']['org_id'] == 'org-a'
    assert session.json()['csrf_token']
    assert set(session.json()['user']) == {'user_id', 'org_id', 'role', 'username'}
    assert session.headers['cache-control'] == 'no-store'
    assert 'session' not in response.json()


@pytest.mark.parametrize('origin', [None, 'null', 'https://pilot.example.test.evil', 'http://pilot.example.test', ORIGIN + '/'])
def test_login_requires_exact_allowed_origin(auth, origin):
    _, _, client = auth
    headers = {'Origin': origin} if origin else {}
    response = client.post('/api/auth/login', headers=headers, json={'username': 'alice', 'password': PASSWORD})
    assert response.status_code == 403


def test_mutations_require_both_exact_origin_and_session_csrf(auth):
    _, _, client = auth
    assert login(client).status_code == 200
    csrf = client.get('/api/auth/session').json()['csrf_token']
    assert client.post('/mutation', headers={'Origin': ORIGIN}).status_code == 403
    assert client.post('/mutation', headers={'Origin': ORIGIN, 'X-CSRF-Token': 'wrong'}).status_code == 403
    assert client.post('/mutation', headers={'Origin': ORIGIN + '.evil', 'X-CSRF-Token': csrf}).status_code == 403
    assert client.post('/mutation', headers={'X-CSRF-Token': csrf}).status_code == 403
    assert client.post('/mutation', headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf}).status_code == 200


def test_logout_revokes_cookie_and_requires_csrf(auth):
    _, store, client = auth
    login(client)
    token = client.cookies.get('insureclear_session')
    csrf = client.get('/api/auth/session').json()['csrf_token']
    assert client.post('/api/auth/logout', headers={'Origin': ORIGIN}).status_code == 403
    response = client.post('/api/auth/logout', headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert store.session(token) is None
    assert client.get('/api/auth/session').status_code == 401


def test_fail_closed_ignores_shared_key_and_missing_configuration(auth, monkeypatch):
    module, _, client = auth
    monkeypatch.setenv('INSURECLEAR_API_KEY', 'synthetic-shared-key')
    assert client.get('/api/auth/session', headers={'X-API-Key': 'synthetic-shared-key'}).status_code == 401
    monkeypatch.setenv('INSURECLEAR_AUTH_MODE', 'legacy')
    assert login(client).status_code == 503
    monkeypatch.setenv('INSURECLEAR_AUTH_MODE', 'accounts')
    monkeypatch.delenv('INSURECLEAR_AUTH_DB', raising=False)
    # Restore the actual lazy resolver without creating any default database.
    monkeypatch.undo()
    monkeypatch.delenv('INSURECLEAR_AUTH_DB', raising=False)
    with pytest.raises(Exception) as exc:
        importlib.reload(module).get_store()
    assert exc.value.status_code == 503


def test_bound_login_body_and_generic_errors(auth):
    _, _, client = auth
    for value in [{'username': 'alice', 'password': 'wrong'}, {'username': 'unknown', 'password': PASSWORD}, {'username': [], 'password': PASSWORD}]:
        response = client.post('/api/auth/login', headers={'Origin': ORIGIN}, json=value)
        assert response.status_code == 401
        assert response.json() == {'detail': 'Invalid username or password'}
        assert response.headers['cache-control'] == 'no-store'
    response = client.post('/api/auth/login', headers={'Origin': ORIGIN}, content=b'x' * 4097)
    assert response.status_code == 413


def test_explicit_local_http_override(auth, monkeypatch):
    _, _, client = auth
    local = 'http://127.0.0.1:5173'
    monkeypatch.setenv('INSURECLEAR_CORS_ORIGINS', local)
    monkeypatch.setenv('INSURECLEAR_AUTH_COOKIE_SECURE', 'false')
    response = client.post('/api/auth/login', headers={'Origin': local},
                           json={'username': 'alice', 'password': PASSWORD})
    assert response.status_code == 200
    assert 'Secure' not in response.headers['set-cookie']
    assert 'HttpOnly' in response.headers['set-cookie']


def test_deeply_nested_json_is_a_generic_invalid_login(auth):
    _, _, client = auth
    response = client.post('/api/auth/login', headers={'Origin': ORIGIN}, content=b'[' * 1500 + b'0' + b']' * 1500)
    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid username or password'}


def test_decoder_recursion_is_a_generic_invalid_login(auth, monkeypatch):
    module, _, client = auth
    def too_deep(*args, **kwargs):
        raise RecursionError("synthetic decoder limit")
    monkeypatch.setattr(module.json, "loads", too_deep)
    response = client.post('/api/auth/login', headers={'Origin': ORIGIN}, content=b'{}')
    assert response.status_code == 401


def test_insecure_cookie_override_rejects_remote_http(auth, monkeypatch):
    _, _, client = auth
    remote = 'http://pilot.example.test'
    monkeypatch.setenv('INSURECLEAR_CORS_ORIGINS', remote)
    monkeypatch.setenv('INSURECLEAR_AUTH_COOKIE_SECURE', 'false')
    response = client.post('/api/auth/login', headers={'Origin': remote},
                           json={'username': 'alice', 'password': PASSWORD})
    assert response.status_code == 503
    assert 'set-cookie' not in response.headers
