"""Load program seed JSON into typed objects.

`app.catalog` may import `app.graph`; the reverse is forbidden. No web framework,
no database. Loading is pure and memoised.

Course rows are kept as plain graph-compatible dicts on ``Catalog.rows`` so the
Stage-1 graph functions run against a loaded catalog unchanged, while
``Catalog.courses`` gives the code-keyed :class:`Course` view the rest of the app
uses. A code can name two rows (a ghost placeholder and its real course); the
code-keyed dict holds the real row and ghosts live on ``Catalog.ghosts``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

__all__ = [
    "CatalogError",
    "Course",
    "Requirement",
    "Program",
    "Term",
    "Catalog",
    "load_all",
    "schools",
    "get",
]


class CatalogError(ValueError):
    """Raised when a seed file is missing, malformed, or an id is unknown."""


@dataclass(frozen=True)
class Term:
    index: int
    key: str
    label: str
    tag: str = ""
    status: str = ""


@dataclass(frozen=True)
class Requirement:
    id: str
    name: str
    min_courses: int
    match: dict[str, list[str]]  # {"explicit": [...]} or {"any_of": [...]}

    @property
    def named_codes(self) -> list[str]:
        """Every course code this requirement's matcher references."""
        out: list[str] = []
        for codes in self.match.values():
            out.extend(codes)
        return out


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    degree: str
    catalog_year: str
    unit_label: str
    unit_abbr: str
    total_units: int
    descriptor: str = ""  # the '<CODE BA · CAMPUS>' sidebar mark
    # presentation copy + derived claims carried from the frontend curriculum
    tab: str = ""
    tiers: tuple[str, ...] = ()
    grad: str = ""
    year: str = ""
    # `key` and the copy below reference the bottleneck course. They are AUTHORED;
    # `app.graph.key_course()` computes it independently. The validator flags a
    # disagreement rather than either side silently overwriting the other.
    key: Optional[str] = None
    keyname: str = ""
    headline: str = ""
    blurb: str = ""
    snapshot: str = ""
    # True when no real requirement matchers have been authored for this program.
    needs_requirements: bool = False


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    units: int
    term: int
    status: str
    group: Optional[str] = None
    tier: Optional[int] = None
    req: tuple[str, ...] = ()
    anti: tuple[str, ...] = ()
    offering: str = "UNKNOWN"
    offering_source: str = "catalog"  # "derived" (hashed) | "catalog" (real)
    needs_review: bool = False
    review_note: Optional[str] = None
    is_gen: bool = False
    is_key: bool = False
    is_alt: bool = False
    is_ghost: bool = False
    note: Optional[str] = None


@dataclass(frozen=True)
class Catalog:
    school: str
    program: Program
    requirements: tuple[Requirement, ...]
    courses: dict[str, Course]        # code-keyed, real (non-ghost) rows
    ghosts: tuple[Course, ...]        # ghost placeholder rows
    terms: tuple[Term, ...]
    rows: tuple[dict, ...]            # every raw row (incl. ghosts), graph-shaped
    groups: tuple[dict, ...] = ()     # derived g-buckets (reproduces the frontend REQS)

    @property
    def program_id(self) -> str:
        return self.program.id

    def graph_courses(self) -> list[dict]:
        """The raw rows as a fresh list, ready for app.graph functions unchanged."""
        return [dict(r) for r in self.rows]


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

_GRAPH_KEYS = ("g", "tier", "req", "anti", "gen", "key", "alt", "ghost", "note")


def _course_from(raw: dict) -> Course:
    return Course(
        code=raw["c"],
        name=raw.get("n", ""),
        units=raw.get("cr", 0),
        term=raw["t"],
        status=raw["s"],
        group=raw.get("g"),
        tier=raw.get("tier"),
        req=tuple(raw.get("req", ())),
        anti=tuple(raw.get("anti", ())),
        offering=raw.get("offering", "UNKNOWN"),
        offering_source=raw.get("offering_source", "catalog"),
        needs_review=bool(raw.get("needs_review", False)),
        review_note=raw.get("review_note"),
        is_gen=bool(raw.get("gen")),
        is_key=bool(raw.get("key")),
        is_alt=bool(raw.get("alt")),
        is_ghost=bool(raw.get("ghost")),
        note=raw.get("note"),
    )


def _graph_row(raw: dict) -> dict:
    """The subset of fields app.graph reads, in the shape it expects."""
    row: dict[str, Any] = {
        "c": raw["c"], "n": raw.get("n", ""), "cr": raw.get("cr", 0),
        "t": raw["t"], "s": raw["s"],
    }
    for k in _GRAPH_KEYS:
        if k in raw:
            row[k] = raw[k]
    return row


def _parse(payload: dict, source: str) -> Catalog:
    try:
        p = payload["program"]
        program = Program(
            id=p["id"], name=p["name"], degree=p.get("degree", ""),
            catalog_year=str(p.get("catalog_year", "")),
            unit_label=p["unit_label"], unit_abbr=p.get("unit_abbr", ""),
            total_units=int(p["total_units"]),
            descriptor=p.get("descriptor", ""),
            tab=p.get("tab", ""), tiers=tuple(p.get("tiers", ())),
            grad=p.get("grad", ""), year=p.get("year", ""),
            key=p.get("key"), keyname=p.get("keyname", ""),
            headline=p.get("headline", ""), blurb=p.get("blurb", ""),
            snapshot=p.get("snapshot", ""),
            needs_requirements=bool(p.get("needs_requirements", False)),
        )
        requirements = tuple(
            Requirement(id=r["id"], name=r["name"],
                        min_courses=int(r.get("min_courses", 0)),
                        match={k: list(v) for k, v in r.get("match", {}).items()})
            for r in payload.get("requirements", [])
        )
        terms = tuple(
            Term(index=t.get("index", i), key=t["key"], label=t["label"],
                 tag=t.get("tag", ""), status=t.get("status", ""))
            for i, t in enumerate(payload.get("terms", []))
        )
        raw_courses = payload["courses"]
    except (KeyError, TypeError, ValueError) as e:
        raise CatalogError(f"{source}: malformed seed structure ({e})") from e

    rows = tuple(_graph_row(c) for c in raw_courses)
    real: dict[str, Course] = {}
    ghosts: list[Course] = []
    for c in raw_courses:
        course = _course_from(c)
        if course.is_ghost:
            ghosts.append(course)
        else:
            # Duplicate real codes are a validator concern; last-wins here keeps
            # loading total. The validator reports the duplication.
            real[course.code] = course

    return Catalog(
        school=payload["school"],
        program=program,
        requirements=requirements,
        courses=real,
        ghosts=tuple(ghosts),
        terms=terms,
        rows=rows,
        groups=tuple(payload.get("groups", [])),
    )


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #

def load_file(path: Path) -> Catalog:
    """Parse one seed file into a Catalog (not memoised; used by tools/tests)."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise CatalogError(f"seed file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise CatalogError(f"{path}: invalid JSON ({e})") from e
    return _parse(payload, str(path))


@lru_cache(maxsize=1)
def load_all() -> dict[str, "Catalog"]:
    """Every seed file under ``data/``, keyed by program id. Memoised."""
    catalogs: dict[str, Catalog] = {}
    for path in sorted(DATA_DIR.glob("*.json")):
        cat = load_file(path)
        if cat.program_id in catalogs:
            raise CatalogError(
                f"duplicate program id {cat.program_id!r} "
                f"({path.name} collides with an earlier seed)"
            )
        catalogs[cat.program_id] = cat
    return catalogs


def get(program_id: str) -> Catalog:
    """The catalog for ``program_id``; raises :class:`CatalogError` if unknown."""
    catalogs = load_all()
    try:
        return catalogs[program_id]
    except KeyError as e:
        known = ", ".join(sorted(catalogs)) or "(none)"
        raise CatalogError(
            f"unknown program id {program_id!r}; known: {known}"
        ) from e


def schools() -> list[dict]:
    """Distinct schools with their programs nested, from a single load_all() pass."""
    by_school: dict[str, dict] = {}
    for cat in load_all().values():
        entry = by_school.setdefault(cat.school, {"school": cat.school, "programs": []})
        entry["programs"].append({
            "id": cat.program.id,
            "name": cat.program.name,
            "degree": cat.program.degree,
            "catalog_year": cat.program.catalog_year,
            "unit_label": cat.program.unit_label,
            "total_units": cat.program.total_units,
            "tab": cat.program.tab,
        })
    for entry in by_school.values():
        entry["programs"].sort(key=lambda p: p["id"])
    return [by_school[k] for k in sorted(by_school)]
