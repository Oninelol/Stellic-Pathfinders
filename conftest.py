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
