"""Synthetic account-store security contracts; no persistent user fixtures."""
import hashlib
import importlib
import importlib.util
import sqlite3

import pytest

PASSWORD = 'synthetic passphrase 19'


@pytest.fixture
def module():
    assert importlib.util.find_spec('tools.auth_store') is not None, 'Account store is missing'
    return importlib.import_module('tools.auth_store')


@pytest.fixture
def store(module, tmp_path):
    return module.AuthStore(tmp_path / 'auth.sqlite3')


def test_password_hash_and_session_secrets_are_not_plaintext(store):
    user = store.create_user('alice', PASSWORD, 'org-a', 'claimant')
    other = store.create_user('bob', PASSWORD, 'org-a', 'reviewer')
    public, token, csrf = store.login('alice', PASSWORD)
    assert public == user
    assert user['user_id'] != other['user_id']
    assert set(public) == {'user_id', 'org_id', 'role', 'username'}
    with sqlite3.connect(store.db_path) as db:
        rows = db.execute('SELECT salt, password_hash FROM auth_users ORDER BY username').fetchall()
        saved = db.execute('SELECT token_hash FROM auth_sessions').fetchone()[0]
    assert rows[0][0] != rows[1][0]
    assert rows[0][1] != rows[1][1]
    assert PASSWORD.encode() not in store.db_path.read_bytes()
    assert token.encode() not in store.db_path.read_bytes()
    assert saved == hashlib.sha256(token.encode()).hexdigest()
    assert len(token) >= 43 and len(csrf) >= 43
    assert store.session(token) == {**user, 'csrf_token': csrf}


def test_real_scrypt_parameters_and_random_salt(store, module, monkeypatch):
    original = module.hashlib.scrypt
    seen = []
    def capture(password, **kwargs):
        seen.append(kwargs)
        return original(password, **kwargs)
    monkeypatch.setattr(module.hashlib, 'scrypt', capture)
    store.create_user('alice', PASSWORD, 'org-a', 'admin')
    assert seen[0]['n'] == 131072
    assert seen[0]['r'] == 8 and seen[0]['p'] == 1
    assert seen[0]['maxmem'] == 256 * 1024 * 1024
    assert len(seen[0]['salt']) >= 16


@pytest.mark.parametrize('password', ['short', 'x' * 129])
def test_password_bounds(store, password):
    with pytest.raises(ValueError):
        store.create_user('alice', password, 'org-a', 'claimant')


@pytest.mark.parametrize('username,org,role', [('', 'org-a', 'claimant'), ('alice', '', 'claimant'), ('alice', 'org-a', 'superuser')])
def test_identity_validation(store, username, org, role):
    with pytest.raises(ValueError):
        store.create_user(username, PASSWORD, org, role)


def test_generic_login_failures(store, module):
    store.create_user('alice', PASSWORD, 'org-a', 'claimant')
    messages = []
    for username, password in [('alice', 'wrong password'), ('nobody', PASSWORD), ('alice', 'x' * 129)]:
        with pytest.raises(module.InvalidLogin) as exc:
            store.login(username, password)
        messages.append(str(exc.value))
    assert len(set(messages)) == 1


def test_expiry_is_absolute_and_logout_revokes(store, module, monkeypatch):
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    store.create_user('alice', PASSWORD, 'org-a', 'claimant')
    _, token, _ = store.login('alice', PASSWORD)
    monkeypatch.setattr(module.time, 'time', lambda: 1000 + 8 * 3600 - 1)
    assert store.session(token)
    monkeypatch.setattr(module.time, 'time', lambda: 1000 + 8 * 3600)
    assert store.session(token) is None
    _, token, _ = store.login('alice', PASSWORD)
    store.logout(token)
    store.logout(token)
    assert store.session(token) is None
    assert store.session('arbitrary-token') is None


def test_reset_and_disable_revoke_all_sessions(store, module):
    user = store.create_user('alice', PASSWORD, 'org-a', 'claimant')
    _, first, _ = store.login('alice', PASSWORD)
    _, second, _ = store.login('alice', PASSWORD)
    store.set_password(user['user_id'], 'another synthetic passphrase')
    assert store.session(first) is None and store.session(second) is None
    with pytest.raises(module.InvalidLogin):
        store.login('alice', PASSWORD)
    _, third, _ = store.login('alice', 'another synthetic passphrase')
    store.disable_user(user['user_id'])
    assert store.session(third) is None
    with pytest.raises(module.InvalidLogin):
        store.login('alice', 'another synthetic passphrase')


def test_throttle_survives_restart_and_precedes_hashing(store, module, monkeypatch):
    user = store.create_user('alice', PASSWORD, 'org-a', 'claimant')
    for _ in range(5):
        with pytest.raises(module.InvalidLogin):
            store.login('alice', 'incorrect synthetic password')
    restarted = module.AuthStore(store.db_path)
    def forbidden(*args, **kwargs):
        pytest.fail('Throttled login must not perform scrypt')
    monkeypatch.setattr(module.hashlib, 'scrypt', forbidden)
    with pytest.raises(module.InvalidLogin):
        restarted.login('alice', PASSWORD)
    assert user['org_id'] == 'org-a'


def test_throttle_recovers_after_window(store, module, monkeypatch):
    now = [1000]
    monkeypatch.setattr(module.time, 'time', lambda: now[0])
    store.create_user('alice', PASSWORD, 'org-a', 'claimant')
    for _ in range(5):
        with pytest.raises(module.InvalidLogin):
            store.login('alice', 'incorrect password')
    now[0] += 15 * 60
    assert store.login('alice', PASSWORD)[0]['username'] == 'alice'


def test_global_throttle_bounds_rotating_names_before_hashing(store, module, monkeypatch):
    # The costly KDF is replaced only here to exercise the admission limit cheaply.
    monkeypatch.setattr(module.hashlib, 'scrypt', lambda *a, **k: bytes(64))
    for index in range(100):
        with pytest.raises(module.InvalidLogin):
            store.login(f'unknown-{index}', PASSWORD)
    def forbidden(*args, **kwargs):
        pytest.fail('Global throttle must run before scrypt')
    monkeypatch.setattr(module.hashlib, 'scrypt', forbidden)
    with pytest.raises(module.InvalidLogin):
        module.AuthStore(store.db_path).login('new-name', PASSWORD)


def test_cli_refuses_password_prompt_that_could_echo(monkeypatch):
    import warnings
    from tools import manage_users
    def unsafe_prompt(*args, **kwargs):
        warnings.warn('Echo is possible', manage_users.getpass.GetPassWarning)
        return PASSWORD
    monkeypatch.setattr(manage_users.getpass, 'getpass', unsafe_prompt)
    with pytest.raises(ValueError, match='hidden'):
        manage_users._prompt_password()


def test_operator_cli_create_reset_disable_use_hidden_prompts(tmp_path, monkeypatch, capsys, module):
    from tools import manage_users
    path = tmp_path / 'operator.sqlite3'
    monkeypatch.setattr(manage_users.getpass, 'getpass', lambda *a, **k: PASSWORD)
    assert manage_users.main(['--db', str(path), 'create', '--username', 'alice', '--org-id', 'org-a', '--role', 'reviewer']) == 0
    store = module.AuthStore(path)
    user, token, _ = store.login('alice', PASSWORD)
    assert manage_users.main(['--db', str(path), 'reset', '--user-id', user['user_id']]) == 0
    assert store.session(token) is None
    _, token, _ = store.login('alice', PASSWORD)
    assert manage_users.main(['--db', str(path), 'disable', '--user-id', user['user_id']]) == 0
    assert store.session(token) is None
    assert PASSWORD not in capsys.readouterr().out
