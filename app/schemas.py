"""Response models and the pure builders that assemble them from a loaded Catalog.

The endpoints in ``app.main`` are one-liners over these builders — no domain logic
in route bodies. Builders take a ``Catalog`` (or the ``load_all`` mapping) and return
plain dicts; the FastAPI ``response_model`` on each route validates and serialises,
which also guarantees the payload shape is identical across all nine programs (only
model fields survive — no program-specific keys can leak).

Imports ``app.graph`` (allowed) and ``app.catalog``; no web/database concerns here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app import catalog, graph

__all__ = [
    "Health", "ProgramSummary", "School", "Term", "Group", "Requirement",
    "Meta", "Node", "Edge", "CourseMap", "Detail",
    "to_health", "to_schools", "to_coursemap", "to_detail",
]


# --------------------------------------------------------------------------- #
# models
# --------------------------------------------------------------------------- #

class Health(BaseModel):
    status: str
    programs: int
    courses: int


class ProgramSummary(BaseModel):
    id: str
    name: str
    degree: str
    catalog_year: str
    unit_label: str
    total_units: int


class School(BaseModel):
    school: str
    programs: list[ProgramSummary]


class Term(BaseModel):
    index: int
    key: str
    label: str
    tag: str = ""
    status: str = ""


class Group(BaseModel):
    group: str
    name: str
    done: int
    in_progress: int
    total: int
    count: str
    missing: list[str]


class Requirement(BaseModel):
    id: str
    name: str
    min_courses: int
    match: dict[str, list[str]]


class Meta(BaseModel):
    done_cr: int
    in_prog_cr: int
    pct: int
    behind_cr: int
    grad_term: str
    class_year: str
    key_code: Optional[str]
    key_name: str
    headline: str
    blurb: str
    snapshot: str


class Node(BaseModel):
    code: str
    title: str
    units: int
    term: int
    status: str
    tier: Optional[int]
    group: Optional[str]
    offering: str
    offering_source: str
    requirement_ids: list[str]
    needs_review: bool
    review_note: Optional[str]
    ghost: bool
    alt: bool
    key: bool


class Edge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from")
    to: str
    kind: str  # "prereq" | "anti"


class CourseMap(BaseModel):
    program_id: str
    school: str
    program_name: str
    unit_label: str
    unit_abbr: str
    total_units: int
    tiers: list[str]
    terms: list[Term]
    groups: list[Group]
    requirements: list[Requirement]
    needs_requirements: bool
    meta: Meta
    nodes: list[Node]
    edges: list[Edge]


class Detail(BaseModel):
    code: str
    title: str
    units: int
    term: int
    status: str
    tier: Optional[int]
    group: Optional[str]
    offering: str
    offering_source: str
    req: list[str]
    anti: list[str]
    needs_review: bool
    review_note: Optional[str]
    ghost: bool
    alt: bool
    key: bool
    blocked_by: list[str]
    direct_unlocks: list[str]
    unlocks: list[str]


# --------------------------------------------------------------------------- #
# builders (pure)
# --------------------------------------------------------------------------- #

def to_health(catalogs: dict[str, catalog.Catalog]) -> dict:
    return {
        "status": "ok",
        "programs": len(catalogs),
        "courses": sum(len(cat.rows) for cat in catalogs.values()),
    }


def to_schools(catalogs: dict[str, catalog.Catalog]) -> list[dict]:
    # catalog.schools() already nests programs under distinct schools in one pass.
    return catalog.schools()


def _requirement_ids_for(cat: catalog.Catalog, code: str) -> list[str]:
    """Which authored requirements this code matches (empty when none are authored)."""
    return [r.id for r in cat.requirements if code in r.named_codes]


def _node(cat: catalog.Catalog, c: catalog.Course) -> dict:
    return {
        "code": c.code, "title": c.name, "units": c.units, "term": c.term,
        "status": c.status, "tier": c.tier, "group": c.group,
        "offering": c.offering, "offering_source": c.offering_source,
        "requirement_ids": _requirement_ids_for(cat, c.code),
        "needs_review": c.needs_review, "review_note": c.review_note,
        "ghost": c.is_ghost, "alt": c.is_alt, "key": c.is_key,
    }


def _edges(cat: catalog.Catalog) -> list[dict]:
    known = set(cat.courses) | {g.code for g in cat.ghosts}
    edges: list[dict] = []
    seen_anti: set[tuple[str, str]] = set()
    # real (non-ghost) rows carry the prereq/anti relationships
    for c in cat.courses.values():
        for r in c.req:
            if r in known:
                edges.append({"from": r, "to": c.code, "kind": "prereq"})
        for a in c.anti:
            if a not in known:
                continue
            pair = tuple(sorted((c.code, a)))
            if pair in seen_anti:
                continue
            seen_anti.add(pair)
            edges.append({"from": pair[0], "to": pair[1], "kind": "anti"})
    return edges


def _meta(cat: catalog.Catalog) -> dict:
    p = cat.program
    rows = cat.graph_courses()
    totals = graph.credit_totals(rows, list(cat.terms), p.total_units)
    done, current = totals["done"], totals["current"]
    key_units = cat.courses[p.key].units if p.key and p.key in cat.courses else 0
    ghost_units = sum(g.units for g in cat.ghosts)
    return {
        "done_cr": done, "in_prog_cr": current,
        "pct": round(done / p.total_units * 100) if p.total_units else 0,
        "behind_cr": key_units + ghost_units,
        "grad_term": p.grad, "class_year": p.year,
        "key_code": p.key, "key_name": p.keyname,
        "headline": p.headline, "blurb": p.blurb, "snapshot": p.snapshot,
    }


def to_coursemap(cat: catalog.Catalog) -> dict:
    p = cat.program
    ghost_by_code = {g.code: g for g in cat.ghosts}
    # one node per raw row (keeps ghosts distinct from their real twin), in seed order
    nodes = []
    for r in cat.rows:
        c = ghost_by_code[r["c"]] if r.get("ghost") else cat.courses[r["c"]]
        nodes.append(_node(cat, c))
    return {
        "program_id": p.id, "school": cat.school, "program_name": p.name,
        "unit_label": p.unit_label, "unit_abbr": p.unit_abbr,
        "total_units": p.total_units, "tiers": list(p.tiers),
        "terms": [
            {"index": t.index, "key": t.key, "label": t.label,
             "tag": t.tag, "status": t.status}
            for t in cat.terms
        ],
        "groups": [dict(g) for g in cat.groups],
        "requirements": [
            {"id": r.id, "name": r.name, "min_courses": r.min_courses, "match": r.match}
            for r in cat.requirements
        ],
        "needs_requirements": p.needs_requirements,
        "meta": _meta(cat),
        "nodes": nodes,
        "edges": _edges(cat),
    }


def to_detail(cat: catalog.Catalog, c: catalog.Course) -> dict:
    rows = cat.graph_courses()
    return {
        "code": c.code, "title": c.name, "units": c.units, "term": c.term,
        "status": c.status, "tier": c.tier, "group": c.group,
        "offering": c.offering, "offering_source": c.offering_source,
        "req": list(c.req), "anti": list(c.anti),
        "needs_review": c.needs_review, "review_note": c.review_note,
        "ghost": c.is_ghost, "alt": c.is_alt, "key": c.is_key,
        "blocked_by": graph.blocked_by(rows, c.code),
        "direct_unlocks": sorted(graph.direct_unlocks(rows, c.code)),
        "unlocks": sorted(graph.unlocks(rows, c.code)),
    }
