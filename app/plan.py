"""Apply a student's plan edits over a published curriculum.

Mirrors the frontend's edit model exactly. The UI holds edits per school as::

    { "moved": { rowId: termIndex }, "added": [courseRow], "removed": [rowId] }
    rowId(c) = c.c + ("#g" if c.ghost else "")

and its ``get COURSES()`` getter applies them over ``BASE_COURSES`` to produce the
live plan. This module reproduces that so the backend can evaluate an edited plan,
not only the published curriculum.

Pure functions, same contract as :mod:`app.graph`: arguments in, a fresh value out,
no mutation of arguments, and **no imports from** ``app`` — the status rule is
duplicated here (a handful of lines) rather than importing ``app.graph.status_for``,
because that constraint is what keeps this module trivially reusable.
"""

from __future__ import annotations

__all__ = ["row_id", "apply_edits"]


def row_id(row: dict) -> str:
    """The frontend's identity for a course row: code, plus ``#g`` for a ghost.

    Ghost placeholders share a code with their real course, so the suffix keeps the
    two distinguishable in ``moved`` / ``removed`` keys.
    """
    return row["c"] + ("#g" if row.get("ghost") else "")


def _current_index(base_rows: list[dict]) -> int:
    """The current-term index, read back from the baked statuses.

    The frontend gets this from ``TERMS.findIndex(st === 'current')``; here the base
    rows already carry a status, and the rows sitting in the current term are marked
    ``current``, so their term index is that same value. Falls back to 3 (the standard
    eight-term layout's in-progress term) when nothing is marked.
    """
    for r in base_rows:
        if r.get("s") == "current" and r.get("t", -1) >= 0:
            return r["t"]
    return 3


def _status_at(cur: int, term_index: int, row: dict) -> str:
    """The status rule from ``graph.status_for``, inlined to avoid an ``app`` import."""
    if row.get("ghost"):
        return "blocked"
    if term_index < 0:
        return "alt"
    if term_index < cur:
        return "done"
    if term_index == cur:
        return "current"
    return "todo" if row.get("key") else "plan"


def apply_edits(base_rows: list[dict], edits: dict) -> list[dict]:
    """The live plan: ``base_rows`` with the student's ``edits`` applied.

    Semantics identical to the JS ``get COURSES()``:

    * a row whose id is in ``removed`` is dropped;
    * a row whose id is in ``moved`` to a **different** term is re-termed, and its
      status recomputed for the new term (moving to the same term is not a move);
    * ``added`` rows are appended verbatim (they already carry their own status).

    Returns fresh dicts; ``base_rows`` and ``edits`` are never mutated.
    """
    edits = edits or {}
    moved = edits.get("moved") or {}
    removed = edits.get("removed") or []
    added = edits.get("added") or []
    removed_set = set(removed)
    cur = _current_index(base_rows)

    out: list[dict] = []
    for c in base_rows:
        rid = row_id(c)
        if rid in removed_set:
            continue
        if rid in moved and moved[rid] != c.get("t"):
            t = moved[rid]
            moved_row = dict(c)
            moved_row["t"] = t
            moved_row["s"] = _status_at(cur, t, c)
            out.append(moved_row)
        else:
            out.append(dict(c))

    out.extend(dict(a) for a in added)
    return out
