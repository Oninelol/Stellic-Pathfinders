"""Vercel serverless entrypoint.

Vercel's Python runtime looks for an ASGI ``app`` in ``api/``. The real
application lives in ``app.main``; here it is mounted under ``/api`` so one
deployment serves both the static planner page and the API from a single
origin, which is why the frontend can call ``/api/...`` with no CORS at all.

Nothing app-specific belongs in this file — it is glue.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The function's working directory is not the repo root, so make the project
# importable before touching anything under `app`.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from app.main import app as compass_api  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Starlette does not run a mounted sub-app's lifespan, so without this the
    # catalog is never warmed and the tables are never created — every request
    # touching the database would 500 with "no such table".
    async with compass_api.router.lifespan_context(compass_api):
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/api", compass_api)
