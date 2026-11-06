"""Invite-only accounts and revocable absolute-lifetime sessions.

The operator supplies an immutable organization identifier; there are no default
accounts. Protect the database and its backups as private authentication data.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

SESSION_SECONDS = 8 * 60 * 60
ROLES = frozenset({'claimant', 'reviewer', 'admin'})
INVALID_LOGIN = 'Invalid username or password'
_IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.@+-]{0,127}$')


class InvalidLogin(ValueError):
    """A deliberately generic credential or admission failure."""


class AuthStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auth_users (
                    user_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    org_id TEXT NOT NULL, role TEXT NOT NULL,
                    salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                    disabled INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES auth_users(user_id),
                    csrf_token TEXT NOT NULL, expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS auth_session_users ON auth_sessions(user_id);
                CREATE TABLE IF NOT EXISTS auth_throttle (
                    bucket TEXT PRIMARY KEY, started_at REAL NOT NULL,
                    attempts INTEGER NOT NULL, expires_at REAL NOT NULL
                );
            ''')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _public(row):
        return {key: row[key] for key in ('user_id', 'org_id', 'role', 'username')}

    @staticmethod
    def _password(password):
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise ValueError('Password must contain 12 to 128 characters')
        return password.encode('utf-8')

    @staticmethod
    def _hash(password: bytes, salt: bytes):
        return hashlib.scrypt(password, salt=salt, n=131072, r=8, p=1,
                              maxmem=256 * 1024 * 1024, dklen=64)

    @staticmethod
    def _username(username):
        if not isinstance(username, str) or not _IDENTIFIER.fullmatch(username):
            raise ValueError('Username must be a bounded identifier')
        return username.lower()

    def create_user(self, username, password, org_id, role):
        username = self._username(username)
        if not isinstance(org_id, str) or not _IDENTIFIER.fullmatch(org_id):
            raise ValueError('Organization must be an explicit identifier')
        if role not in ROLES:
            raise ValueError('Role must be claimant, reviewer or admin')
        salt = secrets.token_bytes(32)
        password_hash = self._hash(self._password(password), salt)
        user = {'user_id': str(uuid.uuid4()), 'org_id': org_id, 'role': role, 'username': username}
        try:
            with self._connect() as db:
                db.execute('INSERT INTO auth_users(user_id,username,org_id,role,salt,password_hash) VALUES(?,?,?,?,?,?)',
                           (user['user_id'], username, org_id, role, salt, password_hash))
        except sqlite3.IntegrityError:
            raise ValueError('Username already exists') from None
        return user

    def _admit(self, username):
        """Reserve attempts transactionally *before* scrypt, across processes.

        Five per normalized username per 15 minutes and 100 globally per minute.
        Stale rows are pruned; the hard cap fails closed under rotating names.
        """
        now = time.time()
        buckets = [('global', 100, 60), ('user:' + hashlib.sha256(username.encode()).hexdigest(), 5, 900)]
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_throttle WHERE expires_at <= ?', (now,))
            rows = {key: db.execute('SELECT * FROM auth_throttle WHERE bucket = ?', (key,)).fetchone()
                    for key, _, _ in buckets}
            if any(rows[key] and rows[key]['attempts'] >= limit for key, limit, _ in buckets):
                return False
            if db.execute('SELECT COUNT(*) FROM auth_throttle').fetchone()[0] >= 10000:
                return False
            for key, _, window in buckets:
                db.execute('''INSERT INTO auth_throttle VALUES(?,?,1,?)
                              ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1''', (key, now, now + window))
        return True

    def login(self, username, password):
        try:
            username = self._username(username)
            encoded = self._password(password)
        except ValueError:
            raise InvalidLogin(INVALID_LOGIN) from None
        if not self._admit(username):
            raise InvalidLogin(INVALID_LOGIN)
        with self._connect() as db:
            user = db.execute('SELECT * FROM auth_users WHERE username = ?', (username,)).fetchone()
        # Unknown names take the same costly path; admission always precedes it.
        candidate = self._hash(encoded, user['salt'] if user else bytes(32))
        if not user or not hmac.compare_digest(candidate, user['password_hash']) or user['disabled']:
            raise InvalidLogin(INVALID_LOGIN)
        raw_token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT * FROM auth_users WHERE user_id = ?', (user['user_id'],)).fetchone()
            # A concurrent operator reset/disable must invalidate in-flight logins.
            if not current or current['disabled'] or current['password_hash'] != user['password_hash']:
                raise InvalidLogin(INVALID_LOGIN)
            db.execute('DELETE FROM auth_sessions WHERE expires_at <= ?', (now,))
            db.execute('INSERT INTO auth_sessions VALUES(?,?,?,?)',
                       (self._token_hash(raw_token), user['user_id'], csrf, now + SESSION_SECONDS))
            db.execute('DELETE FROM auth_throttle WHERE bucket = ?',
                       ('user:' + hashlib.sha256(username.encode()).hexdigest(),))
        return self._public(current), raw_token, csrf

    @staticmethod
    def _token_hash(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def session(self, raw_token):
        if not isinstance(raw_token, str) or not 43 <= len(raw_token) <= 128:
            return None
        with self._connect() as db:
            row = db.execute('''SELECT u.*, s.csrf_token FROM auth_sessions s
                                JOIN auth_users u ON u.user_id=s.user_id
                                WHERE s.token_hash=? AND s.expires_at>? AND u.disabled=0''',
                             (self._token_hash(raw_token), time.time())).fetchone()
        return {**self._public(row), 'csrf_token': row['csrf_token']} if row else None

    def logout(self, raw_token):
        if isinstance(raw_token, str) and len(raw_token) <= 128:
            with self._connect() as db:
                db.execute('DELETE FROM auth_sessions WHERE token_hash=?', (self._token_hash(raw_token),))

    def set_password(self, user_id, password):
        salt = secrets.token_bytes(32)
        password_hash = self._hash(self._password(password), salt)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = db.execute('UPDATE auth_users SET salt=?,password_hash=? WHERE user_id=?',
                                (salt, password_hash, user_id))
            if not result.rowcount:
                raise ValueError('Unknown user')
            db.execute('DELETE FROM auth_sessions WHERE user_id=?', (user_id,))

    def disable_user(self, user_id):
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('UPDATE auth_users SET disabled=1 WHERE user_id=?', (user_id,)).rowcount:
                raise ValueError('Unknown user')
            db.execute('DELETE FROM auth_sessions WHERE user_id=?', (user_id,))
