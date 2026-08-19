"""Test-session setup.

Point the app at a throwaway SQLite file BEFORE any `app.*` import. `app.db` reads
DATABASE_URL at import time, so this must happen at conftest import — otherwise the
first test module to import the app binds the engine to the real dev database and the
suite writes user rows into it.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# A fresh database per test session; never the developer's compass.db.
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"


def pytest_configure(config):
    """Create the user tables once for the whole session.

    Every test module that touches user data needs them; doing it here means a new
    test file does not have to remember (and cannot accidentally point at the dev
    database, which DATABASE_URL above already prevents).
    """
    from app.db import Base, engine
    import app.models  # noqa: F401  — registers the tables on Base
    Base.metadata.create_all(engine)
