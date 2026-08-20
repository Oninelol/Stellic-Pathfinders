#!/usr/bin/env python3
"""Set a new password for an account, for when one is forgotten.

There is no "forgot password" email flow, and the stored hash is scrypt, which
cannot be reversed — so the only way back into a locked-out account is to write
a new hash directly. That needs access to the database, which is the point:
this is an operator tool, not something the app exposes.

    python3 scripts/reset_password.py alex@example.com          # prompts
    python3 scripts/reset_password.py --list                    # show accounts

The password is read with getpass so it never lands in your shell history, and
resetting bumps token_version, which signs that account out everywhere — a
session someone else still holds stops working immediately.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import auth  # noqa: E402
from app.db import DATABASE_URL, SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("email", nargs="?", help="account to reset")
    ap.add_argument("--list", action="store_true", help="list accounts and exit")
    args = ap.parse_args()

    db = SessionLocal()
    print(f"database: {DATABASE_URL}")

    if args.list or not args.email:
        users = list(db.scalars(select(User).order_by(User.email)))
        if not users:
            print("no accounts in this database")
            return 0
        print(f"{len(users)} account(s):")
        for u in users:
            print(f"  {u.email}")
        if not args.email:
            return 0

    email = args.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        print(f"no account with email {email!r} in this database", file=sys.stderr)
        return 1

    new = getpass.getpass(f"new password for {email}: ")
    again = getpass.getpass("confirm: ")
    if new != again:
        print("passwords did not match", file=sys.stderr)
        return 1

    problem = auth.password_problem(new)
    if problem:
        print(problem, file=sys.stderr)
        return 1

    user.password_hash = auth.hash_password(new)
    user.token_version = (user.token_version or 0) + 1   # invalidate old sessions
    db.commit()
    print(f"password updated for {email}; existing sessions were signed out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
