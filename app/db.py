"""SQLite engine and session dependency.

The project's first database, and it holds ONLY user data. The catalog stays as
seed JSON in git — read-only reference material that reloads wholesale, with no
migration history. Nothing here ever creates a catalog table.

SQLite keeps this a single file with no Docker; moving to Postgres later is a
``DATABASE_URL`` change, since the models and migrations are engine-agnostic.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{ROOT / 'compass.db'}")

# check_same_thread=False: FastAPI serves requests on a threadpool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
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


def get_db():
    """FastAPI dependency yielding a session that always closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
