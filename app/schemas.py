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
    tab: str
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
    req: list[str]
    anti: list[str]
    note: Optional[str]
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
    program: str          # the '<CODE BA · CAMPUS>' descriptor
    tab: str              # short label for the selector
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
        "req": list(c.req), "anti": list(c.anti), "note": c.note,
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
        "program": p.descriptor, "tab": p.tab,
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


# --------------------------------------------------------------------------- #
# Phase 3 — stateless evaluation
# --------------------------------------------------------------------------- #

class Edits(BaseModel):
    """The client's edit model, exactly as the board holds it."""
    moved: dict[str, int] = {}
    added: list[dict] = []
    removed: list[str] = []


class EvaluateRequest(BaseModel):
    edits: Edits = Edits()


class BlockedItem(BaseModel):
    code: str
    term: int
    missing: list[str]


class ConflictItem(BaseModel):
    a: str
    b: str
    one_sided: bool


class Totals(BaseModel):
    per_term: list[dict]
    done: int
    current: int
    planned: int
    remaining: int
    total: int


class EvaluateResponse(BaseModel):
    blocked: list[BlockedItem]
    conflicts: list[ConflictItem]
    totals: Totals
    key_course: Optional[str]
    groups: list[Group]
    unknown_codes: list[str]


GROUP_LABELS = {
    "major": "Major sequence", "math": "Mathematics", "sci": "Science",
    "huss": "Humanities & social sciences", "free": "Free electives",
}
_GROUP_ORDER = ["major", "math", "sci", "huss", "free"]


def _groups_from_rows(rows: list[dict], terms: list[dict]) -> list[dict]:
    """Requirement group buckets recomputed from the live plan.

    Mirrors ``curricula.derive_groups`` but over evaluated rows, so the buckets
    reflect the student's edits rather than the published curriculum.
    """
    out = []
    for g in _GROUP_ORDER:
        members = [r for r in rows if r.get("g") == g and not r.get("ghost") and not r.get("alt")]
        if not members:
            continue
        done = sum(1 for r in members if r["s"] == "done")
        prog = sum(1 for r in members if r["s"] == "current")
        missing = [r["c"] for r in members if r["s"] in ("todo", "plan")][:5]
        out.append({
            "group": g, "name": GROUP_LABELS[g], "done": done, "in_progress": prog,
            "total": len(members), "count": f"{done} of {len(members)} courses",
            "missing": missing,
        })
    return out


def to_evaluate(cat: catalog.Catalog, rows: list[dict]) -> dict:
    """Evaluate an already-edited plan. Pure: rows in, verdict out.

    ``rows`` is the output of ``plan.apply_edits`` — statuses are recomputed from term
    position via ``graph.status_for`` so a moved course reflects its new term rather
    than the status baked into the seed.
    """
    terms = [{"st": t.status} for t in cat.terms]
    live: list[dict] = []
    for r in rows:
        row = dict(r)
        row["s"] = graph.status_for(terms, row.get("t", -1), row)
        live.append(row)

    known = set(cat.courses) | {g.code for g in cat.ghosts}
    unknown = sorted({r["c"] for r in live if r["c"] not in known})

    blocked = []
    for r in live:
        if r.get("ghost") or r.get("t", -1) < 0:
            continue
        missing = graph.blocked_by(live, r["c"])
        if missing:
            blocked.append({"code": r["c"], "term": r["t"], "missing": missing})
    blocked.sort(key=lambda b: (b["term"], b["code"]))

    return {
        "blocked": blocked,
        "conflicts": graph.conflicts(live),
        "totals": graph.credit_totals(live, list(cat.terms), cat.program.total_units),
        "key_course": graph.key_course(live),
        "groups": _groups_from_rows(live, terms),
        "unknown_codes": unknown,
    }


def evaluate_edits(cat: catalog.Catalog, edits: dict) -> dict:
    """Apply ``edits`` to the published curriculum and evaluate the result.

    The ONE code path for evaluation. Both ``POST /programs/{id}/evaluate`` and
    ``GET /me/plans/{id}/evaluate`` call this, so the two can never diverge.
    """
    from app import plan as plan_mod
    rows = plan_mod.apply_edits(cat.graph_courses(), edits or {})
    return to_evaluate(cat, rows)


def term_range_error(cat: catalog.Catalog, edits: dict) -> Optional[str]:
    """A message naming the valid range if any edit targets a term outside it."""
    n = len(cat.terms)
    bad: list[str] = []
    for rid, t in (edits.get("moved") or {}).items():
        if not isinstance(t, int) or not (-1 <= t < n):
            bad.append(f"{rid}->{t}")
    for a in (edits.get("added") or []):
        t = a.get("t")
        if not isinstance(t, int) or not (-1 <= t < n):
            bad.append(f"{a.get('c')}->{t}")
    if not bad:
        return None
    return (f"term index out of range for {', '.join(bad)}; "
            f"valid terms are 0..{n - 1} (or -1 for unscheduled)")
