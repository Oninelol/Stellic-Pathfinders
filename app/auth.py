"""Email + password authentication, and the ``current_user`` dependency.

Deliberate choices, since rolling auth is normally the wrong call:

* **Passwords** are hashed with :func:`hashlib.scrypt` (stdlib, memory-hard), a
  fresh 16-byte salt per user, and compared with :func:`hmac.compare_digest`.
  Plaintext is never stored or logged.
* **Sessions** are stateless signed JWTs (HS256). No session table to grow, and
  "sign out everywhere" works by bumping ``User.token_version``, which every token
  carries and every verification checks.
* **"Stay signed in"** is the token lifetime, not a second mechanism: a normal login
  gets 12 hours, ``remember_me`` gets 90 days. The client decides where to keep it
  (localStorage when remembered, sessionStorage when not).

``SECRET_KEY`` must be set in production; a dev default is used locally so a fresh
clone runs, and the app logs nothing that would leak it.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

DEV_SECRET_KEY = "dev-only-insecure-key-change-me-in-production-please"
SECRET_KEY = os.environ.get("SECRET_KEY") or DEV_SECRET_KEY
ALGORITHM = "HS256"
SESSION_HOURS = 12          # a normal login
REMEMBER_DAYS = 90          # "keep me signed in"

_N, _R, _P = 2 ** 14, 8, 1  # scrypt cost parameters


# --------------------------------------------------------------------------- #
# passwords
# --------------------------------------------------------------------------- #

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                            n=int(n), r=int(r), p=int(p), dklen=len(hash_hex) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


def password_problem(password: str) -> Optional[str]:
    """A human-readable reason the password is unacceptable, or None."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 200:
        return "Password must be under 200 characters."
    return None


# --------------------------------------------------------------------------- #
# tokens
# --------------------------------------------------------------------------- #

def create_token(user: User, remember: bool = False) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``. ``remember`` picks the lifetime."""
    delta = timedelta(days=REMEMBER_DAYS) if remember else timedelta(hours=SESSION_HOURS)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "ver": user.token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
        "remember": bool(remember),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), int(delta.total_seconds())


class AuthError(HTTPException):
    """401 with a reason the client can distinguish (no token vs bad vs expired)."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(status_code=401, detail={"error": reason, "message": message})


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    return header[7:].strip() or None


def _user_from_token(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("token_expired", "Your session expired — please sign in again.")
    except jwt.InvalidTokenError:
        raise AuthError("token_invalid", "That sign-in token is not valid.")
    user = db.get(User, int(payload.get("sub", 0) or 0))
    if user is None:
        raise AuthError("token_invalid", "That account no longer exists.")
    if payload.get("ver") != user.token_version:
        raise AuthError("token_revoked", "You were signed out — please sign in again.")
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Require a signed-in user. 401 (never 403/500) when absent or unusable."""
    token = _bearer(request)
    if not token:
        raise AuthError("no_token", "Sign in to use this.")
    return _user_from_token(token, db)


def optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """The signed-in user if there is one; None for anonymous callers.

    Used by endpoints that must keep working without an Authorization header.
    """
    token = _bearer(request)
    if not token:
        return None
    try:
        return _user_from_token(token, db)
    except HTTPException:
        return None
