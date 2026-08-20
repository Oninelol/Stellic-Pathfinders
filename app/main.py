"""Compass Planner read-only API (Phase 1).

Thin FastAPI shell over the pure modules. No database, ORM, migrations, auth, or
write endpoints — those are later phases. The catalog loads once at startup
(``catalog.load_all()`` is memoised) and every endpoint is a comprehension over it.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import auth, catalog, db, schemas
from app.routes_user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the memoised catalog at startup so the first request is not slow and a
    # broken seed fails loudly here rather than on a random request.
    catalog.load_all.cache_clear()
    catalog.load_all()
    # No migration step exists on a serverless host, so make sure the tables are
    # there before the first request tries to read them.
    db.ensure_schema()
    for line in _deployment_warnings():
        print("WARNING:", line, flush=True)
    yield


def _deployment_warnings() -> list[str]:
    """Conditions that let the app boot but will bite in production."""
    out = []
    if auth.SECRET_KEY == auth.DEV_SECRET_KEY:
        out.append(
            "SECRET_KEY is unset, so sessions are signed with the public dev key "
            "and anyone can forge a login. Set SECRET_KEY before real use.")
    if db.IS_EPHEMERAL:
        out.append(
            "No DATABASE_URL, and the app directory is read-only, so data is in "
            "/tmp. That disk is per-instance and cleared on cold starts: accounts "
            "will disappear. Point DATABASE_URL at Postgres.")
    return out


app = FastAPI(title="Compass Planner API", version="1.0.0", lifespan=lifespan)

# CORS: localhost is always allowed for development. FRONTEND_ORIGIN adds the
# deployed frontend when it is served from a DIFFERENT origin than this API —
# the apex and the www host are separate origins to a browser, so it takes a
# comma-separated list rather than a single value.
_frontend_origins = [o.strip().rstrip("/")
                     for o in os.environ.get("FRONTEND_ORIGIN", "").split(",")
                     if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


def _get_program(program_id: str) -> catalog.Catalog:
    try:
        return catalog.get(program_id)
    except catalog.CatalogError:
        known = sorted(catalog.load_all())
        raise HTTPException(
            status_code=404,
            detail={"error": f"unknown program id {program_id!r}", "known_programs": known},
        )


@app.get("/healthz", response_model=schemas.Health)
def healthz() -> dict:
    return schemas.to_health(catalog.load_all())


@app.get("/schools", response_model=list[schemas.School])
def schools() -> list[dict]:
    return schemas.to_schools(catalog.load_all())


@app.get("/programs/{program_id}/coursemap", response_model=schemas.CourseMap)
def coursemap(program_id: str) -> dict:
    return schemas.to_coursemap(_get_program(program_id))


@app.get("/programs/{program_id}/courses/{code}", response_model=schemas.Detail)
def course_detail(program_id: str, code: str) -> dict:
    cat = _get_program(program_id)
    course = cat.courses.get(code)
    if course is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"course {code!r} not in program {program_id!r}",
                "known_courses": sorted(cat.courses),
            },
        )
    return schemas.to_detail(cat, course)


# --------------------------------------------------------------------------- #
# Phase 3 — stateless evaluation
# --------------------------------------------------------------------------- #

@app.post("/programs/{program_id}/evaluate", response_model=schemas.EvaluateResponse)
def evaluate(program_id: str, body: schemas.EvaluateRequest = Body(default=None)) -> dict:
    """Evaluate a plan expressed as edits over the published curriculum.

    Stateless: nothing is stored, cached per-user, or written. Unknown course codes
    are reported in ``unknown_codes`` and the request still succeeds — a transfer
    credit deserves an answer, not a 422. Only an out-of-range term is a 422.
    """
    cat = _get_program(program_id)
    edits = (body.edits.model_dump() if body and body.edits else {})
    msg = schemas.term_range_error(cat, edits)
    if msg:
        raise HTTPException(status_code=422, detail={"error": msg})
    return schemas.evaluate_edits(cat, edits)


# Auth + per-user plans. Catalog and evaluate above stay public and anonymous.
app.include_router(user_router)
