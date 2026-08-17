"""Pure graph/business logic for the degree planner.

Ported from the ``GRAPH`` logic embedded in ``Compass Planner.html``. This module
imports nothing from ``app`` and nothing from any web/database framework: it is a
set of pure functions over the course-dict shape, so it can be unit-tested in
isolation and later dropped straight into HTTP endpoint bodies.

Course dict shape (only the keys these functions read are documented here)::

    {
      "c":    str,        # course code, e.g. "CS 210"  (NOT unique: a ghost row
                          #                               and its real row share it)
      "n":    str,        # display name
      "cr":   int,        # credits / units
      "t":    int,        # term index; -1 means unscheduled
      "s":    str,        # done | current | plan | todo | blocked | alt
      "tier": int,        # depth in the major sequence; absent on gen-ed rows
      "req":  list[str],  # prerequisite codes, AND semantics
      "anti": list[str],  # mutually-exclusive codes
      # optional flags: "gen", "key", "alt", "ghost" (+ "note")
    }

Every function takes ``courses`` (and ``terms`` where needed) as its first
argument, returns a fresh value, and mutates nothing — including its arguments.
Malformed input raises :class:`CatalogError` rather than returning a sentinel.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "CatalogError",
    "blocked_by",
    "unlocks",
    "direct_unlocks",
    "credit_totals",
    "conflicts",
    "key_course",
]


class CatalogError(ValueError):
    """Raised on malformed catalog input (bad shape, unknown code, cycle)."""


# --------------------------------------------------------------------------- #
# validation + small shared helpers
# --------------------------------------------------------------------------- #

def _validate(courses: object) -> list[dict]:
    """Confirm ``courses`` is a list of well-formed course dicts; return it.

    Checks only the structural invariants the functions below rely on. Cheap and
    idempotent — every public function calls it first so a malformed catalog is
    rejected at the boundary instead of surfacing as a confusing KeyError later.
    """
    if not isinstance(courses, list):
        raise CatalogError(f"courses must be a list, got {type(courses).__name__}")
    for i, c in enumerate(courses):
        if not isinstance(c, dict):
            raise CatalogError(f"course #{i} is not a dict: {c!r}")
        if not isinstance(c.get("c"), str) or not c["c"]:
            raise CatalogError(f"course #{i} has no valid 'c' code: {c!r}")
        if not isinstance(c.get("t"), int) or isinstance(c.get("t"), bool):
            raise CatalogError(f"course {c.get('c')!r} has non-int 't': {c.get('t')!r}")
        if not isinstance(c.get("s"), str):
            raise CatalogError(f"course {c['c']!r} has non-str 's': {c.get('s')!r}")
        if not isinstance(c.get("cr", 0), int) or isinstance(c.get("cr", 0), bool):
            raise CatalogError(f"course {c['c']!r} has non-int 'cr': {c.get('cr')!r}")
        for field in ("req", "anti"):
            v = c.get(field)
            if v is not None and (
                not isinstance(v, list) or any(not isinstance(x, str) for x in v)
            ):
                raise CatalogError(f"course {c['c']!r} has bad {field!r}: {v!r}")
    return courses


def _provider_terms(courses: list[dict]) -> dict[str, list[int]]:
    """Map each code to the term indices where it is a valid prerequisite provider.

    Ghost rows are display artifacts and never satisfy a prerequisite, so they are
    excluded. Unscheduled rows (``t == -1``) satisfy nothing either.
    """
    out: dict[str, list[int]] = {}
    for c in courses:
        if c.get("ghost"):
            continue
        if c["t"] == -1:
            continue
        out.setdefault(c["c"], []).append(c["t"])
    return out


def _row_blocked(row: dict, provider_terms: dict[str, list[int]]) -> list[str]:
    """Prereq codes of a single row not scheduled in a strictly earlier term."""
    if row.get("gen"):
        return []
    t = row["t"]
    if t == -1:  # unscheduled: cannot be blocked
        return []
    out: list[str] = []
    for r in (row.get("req") or []):
        if not any(pt < t for pt in provider_terms.get(r, ())):
            out.append(r)
    return out


def _subject_row(courses: list[dict], code: str) -> Optional[dict]:
    """The row a code-level query is about: the real (non-ghost) course.

    A code can name two rows — a ``ghost`` placeholder and the real course. Queries
    are about the real one. Among real rows (there is normally exactly one) prefer a
    scheduled row with the earliest term, so a code that is both scheduled and has an
    unscheduled ``alt`` twin resolves to the scheduled instance. Falls back to a
    ghost only when no real row exists.
    """
    real = [c for c in courses if c["c"] == code and not c.get("ghost")]
    if real:
        scheduled = [c for c in real if c["t"] != -1]
        pool = scheduled or real
        return min(pool, key=lambda c: (c["t"] if c["t"] != -1 else 1 << 30))
    ghosts = [c for c in courses if c["c"] == code]
    return ghosts[0] if ghosts else None


def _reverse_adjacency(courses: list[dict]) -> dict[str, set[str]]:
    """provider code -> set of codes that list it as a prerequisite (ghosts excluded)."""
    adj: dict[str, set[str]] = {}
    for c in courses:
        if c.get("ghost"):
            continue
        for r in (c.get("req") or []):
            adj.setdefault(r, set()).add(c["c"])
    return adj


# --------------------------------------------------------------------------- #
# the five functions
# --------------------------------------------------------------------------- #

def blocked_by(courses: list[dict], code: str) -> list[str]:
    """Prerequisite codes of ``code`` not scheduled in a strictly earlier term.

    An empty list means the course is not blocked. A ``req`` code absent from the
    catalog counts as unsatisfied (blocked), not ignored. Unscheduled and gen-ed
    rows are never blocked. Prereqs are returned in the order they are authored.
    """
    _validate(courses)
    subject = _subject_row(courses, code)
    if subject is None:
        raise CatalogError(f"unknown course code: {code!r}")
    return _row_blocked(subject, _provider_terms(courses))


def direct_unlocks(courses: list[dict], code: str) -> set[str]:
    """Codes that list ``code`` as a direct prerequisite (one hop). Excludes ``code``.

    Includes ``alt`` and unscheduled dependents — they are still real dependents.
    Ghost rows are excluded (they duplicate a real course).
    """
    _validate(courses)
    out = {dep for dep in _reverse_adjacency(courses).get(code, set())}
    out.discard(code)
    return out


def unlocks(courses: list[dict], code: str) -> set[str]:
    """Transitive reverse-dependency closure of ``code`` (excludes ``code`` itself).

    Includes ``alt`` and unscheduled dependents. Raises :class:`CatalogError` naming
    the cycle if the dependency graph reachable from ``code`` contains one, rather
    than recursing forever.
    """
    _validate(courses)
    adj = _reverse_adjacency(courses)
    result: set[str] = set()
    on_path: list[str] = []
    on_path_set: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> None:
        on_path.append(node)
        on_path_set.add(node)
        for dep in sorted(adj.get(node, ())):
            if dep in on_path_set:
                cycle = on_path[on_path.index(dep):] + [dep]
                raise CatalogError("cyclic prerequisites: " + " -> ".join(cycle))
            result.add(dep)
            if dep not in done:
                visit(dep)
        on_path.pop()
        on_path_set.discard(node)
        done.add(node)

    visit(code)
    result.discard(code)
    return result


def credit_totals(
    courses: list[dict], terms: list[dict], total: Optional[int] = None
) -> dict:
    """Per-term and by-status credit sums.

    Returns::

        {"per_term": [{"term_index": int, "credits": int}, ...],
         "done": int, "current": int, "planned": int,
         "remaining": int, "total": int}

    Ghost rows are excluded from every sum (they duplicate a real course). ``alt``
    rows parked at ``t == -1`` are excluded (they are not scheduled). ``total`` is a
    program constant supplied by the caller and is never derived by summing; when it
    is omitted, ``total`` and ``remaining`` report 0 (remaining is only meaningful
    against an explicit program total).
    """
    _validate(courses)
    real = [c for c in courses if not c.get("ghost")]

    per_term = [
        {"term_index": i, "credits": sum(c["cr"] for c in real if c["t"] == i)}
        for i in range(len(terms))
    ]

    done = sum(c["cr"] for c in real if c["s"] == "done")
    current = sum(c["cr"] for c in real if c["s"] == "current")
    planned = sum(
        c["cr"] for c in real if c["s"] in ("plan", "todo", "blocked") and c["t"] != -1
    )

    total_val = total if total is not None else 0
    remaining = total_val - (done + current + planned) if total is not None else 0

    return {
        "per_term": per_term,
        "done": done,
        "current": current,
        "planned": planned,
        "remaining": remaining,
        "total": total_val,
    }


def conflicts(courses: list[dict]) -> list[dict]:
    """Anti-requisite pairs where both courses are scheduled.

    Considers only scheduled (``t != -1``), non-ghost rows. Returns each pair once,
    with the two codes sorted, as ``{"a": str, "b": str, "one_sided": bool}``. The
    ``anti`` relation is not guaranteed symmetric in the data, so a one-directional
    declaration still counts as a conflict and is flagged ``one_sided=True`` so the
    dataset can be corrected later.
    """
    _validate(courses)
    scheduled = [c for c in courses if c["t"] != -1 and not c.get("ghost")]
    codes = {c["c"] for c in scheduled}
    anti_by: dict[str, set[str]] = {}
    for c in scheduled:
        anti_by.setdefault(c["c"], set()).update(c.get("anti") or [])

    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for a in codes:
        for b in anti_by.get(a, set()):
            if b not in codes:  # the other side must also be scheduled
                continue
            pair = tuple(sorted((a, b)))
            if pair in seen:
                continue
            seen.add(pair)
            two_sided = a in anti_by.get(b, set()) and b in anti_by.get(a, set())
            out.append({"a": pair[0], "b": pair[1], "one_sided": not two_sided})
    out.sort(key=lambda d: (d["a"], d["b"]))
    return out


def key_course(courses: list[dict]) -> Optional[str]:
    """The bottleneck course: the largest blocked-downstream set.

    Candidates are courses whose own status is ``todo``/``blocked`` or which are
    scheduled but currently blocked by an unmet prerequisite. Each candidate is
    ranked by the number of its transitive dependents that are **not yet done** —
    dependents already completed do not make a course a bottleneck, so raw
    ``unlocks`` size is the wrong measure. Ties break on lower ``tier`` then code, so
    the result is stable. Returns ``None`` when nothing qualifies (no candidate has a
    blocked dependent).
    """
    _validate(courses)
    provider_terms = _provider_terms(courses)
    done_codes = {c["c"] for c in courses if not c.get("ghost") and c["s"] == "done"}

    # candidate row per code, preferring the lowest tier
    best: dict[str, dict] = {}
    for c in courses:
        if c.get("ghost"):
            continue
        is_candidate = c["s"] in ("todo", "blocked") or (
            c["t"] != -1 and _row_blocked(c, provider_terms)
        )
        if not is_candidate:
            continue
        cur = best.get(c["c"])
        if cur is None or c.get("tier", 1 << 30) < cur.get("tier", 1 << 30):
            best[c["c"]] = c

    scored: list[tuple[int, int, str]] = []
    for code, row in best.items():
        blocked_downstream = {d for d in unlocks(courses, code) if d not in done_codes}
        if blocked_downstream:
            scored.append((len(blocked_downstream), row.get("tier", 1 << 30), code))

    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    return scored[0][2]
