"""Operator-only account administration: python -m tools.manage_users --help.

No public registration/reset. Passwords are read with getpass, never arguments,
logs or output. Set INSURECLEAR_AUTH_DB or pass --db to a private auth database.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import warnings

from tools.auth_store import AuthStore, ROLES


def _prompt_password():
    # getpass otherwise falls back to visible stdin when no terminal is available.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            password = getpass.getpass('New password (12-128 characters): ')
            confirmation = getpass.getpass('Confirm password: ')
        except getpass.GetPassWarning:
            raise ValueError('Password entry requires a terminal with hidden input') from None
    if password != confirmation:
        raise ValueError('Passwords do not match')
    return password


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=os.getenv('INSURECLEAR_AUTH_DB'))
    actions = parser.add_subparsers(dest='action', required=True)
    create = actions.add_parser('create')
    create.add_argument('--username', required=True)
    create.add_argument('--org-id', required=True)
    create.add_argument('--role', choices=sorted(ROLES), required=True)
    for action in ('reset', 'disable'):
        actions.add_parser(action).add_argument('--user-id', required=True)
    args = parser.parse_args(argv)
    if not args.db:
        parser.error('Set INSURECLEAR_AUTH_DB or provide --db')
    try:
        password = _prompt_password() if args.action in {'create', 'reset'} else None
        store = AuthStore(args.db)
        if args.action == 'create':
            print(json.dumps(store.create_user(args.username, password, args.org_id, args.role)))
        elif args.action == 'reset':
            store.set_password(args.user_id, password)
            print('Password reset; all sessions revoked')
        else:
            store.disable_user(args.user_id)
            print('User disabled; all sessions revoked')
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
