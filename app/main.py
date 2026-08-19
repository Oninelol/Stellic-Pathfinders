"""Compass Planner read-only API (Phase 1).

Thin FastAPI shell over the pure modules. No database, ORM, migrations, auth, or
write endpoints — those are later phases. The catalog loads once at startup
(``catalog.load_all()`` is memoised) and every endpoint is a comprehension over it.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import catalog, schemas


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the memoised catalog at startup so the first request is not slow and a
    # broken seed fails loudly here rather than on a random request.
    catalog.load_all.cache_clear()
    catalog.load_all()
    yield


app = FastAPI(title="Compass Planner API", version="1.0.0", lifespan=lifespan)

# CORS: local dev origins only. Phase 6 sets the deployed frontend origin from env.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET"],
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
