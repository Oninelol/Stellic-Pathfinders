"""SQLite engine and session dependency.

The project's first database, and it holds ONLY user data. The catalog stays as
seed JSON in git — read-only reference material that reloads wholesale, with no
migration history. Nothing here ever creates a catalog table.

SQLite keeps this a single file with no Docker; moving to Postgres later is a
``DATABASE_URL`` change, since the models and migrations are engine-agnostic.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parent.parent


def _normalise(url: str) -> str:
    """Clean up a hand-pasted URL and give it an explicit driver.

    Dashboard-set variables routinely arrive with a trailing newline or wrapped
    in quotes, and SQLAlchemy rejects both with an opaque parse error, so strip
    them here rather than let the process die on import.
    """
    url = url.strip().strip('"').strip("'").strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _default_url() -> str:
    """SQLite next to the code, unless that directory is read-only.

    A serverless deployment ships a read-only filesystem, so the usual path
    cannot even be created and every request would fail. Falling back to /tmp
    keeps the deployment alive, but that disk is per-instance and wiped on every
    cold start: accounts created there vanish. Set DATABASE_URL to a real
    Postgres URL for anything you expect to persist.
    """
    if os.access(ROOT, os.W_OK):
        return f"sqlite:///{ROOT / 'compass.db'}"
    return "sqlite:////tmp/compass.db"


# `.get(key, default)` is deliberately not used: a variable that exists but is
# empty must fall back too, and an empty string is exactly what SQLAlchemy
# cannot parse.
DATABASE_URL = _normalise(os.environ.get("DATABASE_URL", "")) or _normalise(_default_url())
IS_EPHEMERAL = DATABASE_URL == "sqlite:////tmp/compass.db"

# check_same_thread=False: FastAPI serves requests on a threadpool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
def _redacted(url: str) -> str:
    """The URL with any password blanked, safe to put in a log line."""
    return re.sub(r"//([^:/@]+):[^@]*@", r"//\1:***@", url)


try:
    engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
except ArgumentError as exc:
    # Dying here kills the whole process at import time, and the stack trace
    # says nothing about which setting is wrong. Say it plainly instead.
    raise RuntimeError(
        f"DATABASE_URL cannot be parsed: {exc}. Got {_redacted(DATABASE_URL)!r}. "
        "Expected a URL like postgresql://user:password@host:5432/dbname — check "
        "for an empty value, surrounding quotes, a 'psql ' prefix, or a pasted "
        "newline."
    ) from exc
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _sqlite_fk_pragma(dbapi_conn, _):
    """SQLite ignores ON DELETE CASCADE unless foreign keys are switched on."""
    if DATABASE_URL.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    pass


def ensure_schema() -> None:
    """Create any missing tables.

    Alembic stays the source of truth for local work and normal deploys; a
    serverless host has no place to run ``alembic upgrade``, so a fresh database
    would otherwise have no tables and every request would 500. This creates
    what is absent and touches nothing that already exists — it will NOT add a
    column to a table created by an older revision, so run the migrations when
    upgrading an existing database.
    """
    from app import models  # noqa: F401  — imports register the tables on Base

    Base.metadata.create_all(engine)


def get_db():
    """FastAPI dependency yielding a session that always closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
