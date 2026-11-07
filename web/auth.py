"""Cookie-only account authentication; configure before mounting the router.

INSURECLEAR_AUTH_MODE=accounts and INSURECLEAR_AUTH_DB are required. Allowed
Origins come from the exact INSURECLEAR_CORS_ORIGINS allowlist. Cookies default
to Secure; INSURECLEAR_AUTH_COOKIE_SECURE=false is an explicit HTTP development
only override. Production must use HTTPS and restricted private database paths.
"""
from __future__ import annotations

import hmac
import json
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from tools.auth_store import AuthStore, InvalidLogin, INVALID_LOGIN, SESSION_SECONDS

router = APIRouter(prefix='/api/auth', tags=['auth'])
COOKIE_NAME = 'insureclear_session'
NO_STORE = {'Cache-Control': 'no-store'}


@lru_cache(maxsize=4)
def _store_for_path(path):
    return AuthStore(path)


def get_store():
    """Resolve lazily so importing auth never creates a database or an account."""
    path = os.getenv('INSURECLEAR_AUTH_DB', '').strip()
    if not path:
        raise HTTPException(503, 'Account authentication is not configured', headers=NO_STORE)
    return _store_for_path(str(Path(path).resolve()))


def auth_mode():
    return os.getenv('INSURECLEAR_AUTH_MODE', 'accounts').strip().lower()


def _accounts_enabled():
    if auth_mode() != 'accounts':
        raise HTTPException(503, 'Account authentication is not configured', headers=NO_STORE)


def browser_origins():
    return [value.strip() for value in os.getenv(
        'INSURECLEAR_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if value.strip()]


def secure_cookie():
    if os.getenv('INSURECLEAR_AUTH_COOKIE_SECURE', 'true').lower() != 'false':
        return True
    origins = [urlsplit(origin) for origin in browser_origins()]
    if not origins or any(origin.scheme != 'http' or origin.hostname not in {'localhost', '127.0.0.1', '::1'}
                          for origin in origins):
        raise HTTPException(503, 'Insecure cookies are allowed only for local HTTP development', headers=NO_STORE)
    return False


def _require_origin(request):
    allowed = browser_origins()
    origin = request.headers.get('origin')
    if not origin or origin == 'null' or origin == '*' or origin not in allowed:
        raise HTTPException(403, 'Origin is not allowed', headers=NO_STORE)


def current_principal(request: Request) -> dict:
    _accounts_enabled()
    principal = get_store().session(request.cookies.get(COOKIE_NAME))
    if not principal:
        raise HTTPException(401, 'Authentication required', headers=NO_STORE)
    return principal


def require_mutation(request: Request, principal: dict):
    _require_origin(request)
    supplied, expected = request.headers.get('x-csrf-token', ''), principal.get('csrf_token', '')
    if not supplied or not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(403, 'Invalid CSRF token', headers=NO_STORE)


@router.post('/login')
async def login(request: Request):
    _accounts_enabled()
    _require_origin(request)
    secure = secure_cookie()
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 4096:
            raise HTTPException(413, 'Login body exceeds the limit', headers=NO_STORE)
        body.extend(chunk)
    try:
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get('username'), str) or not isinstance(data.get('password'), str):
            raise ValueError()
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(401, INVALID_LOGIN, headers=NO_STORE) from None
    try:
        public, token, csrf = await run_in_threadpool(get_store().login, data['username'], data['password'])
    except InvalidLogin:
        raise HTTPException(401, INVALID_LOGIN, headers=NO_STORE) from None
    response = JSONResponse({'user': public, 'csrf_token': csrf}, headers=NO_STORE)
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=secure, samesite='lax', path='/')
    return response


@router.get('/session')
def session(principal: dict = Depends(current_principal)):
    public = {key: value for key, value in principal.items() if key != 'csrf_token'}
    return JSONResponse({'user': public, 'csrf_token': principal['csrf_token']}, headers=NO_STORE)


@router.post('/logout')
def logout(request: Request, principal: dict = Depends(current_principal)):
    require_mutation(request, principal)
    secure = secure_cookie()
    get_store().logout(request.cookies.get(COOKIE_NAME))
    response = JSONResponse({'ok': True}, headers=NO_STORE)
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, secure=secure, samesite='lax')
    return response
