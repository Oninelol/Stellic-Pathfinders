#!/usr/bin/env python3
"""Validate every program seed file. Exit non-zero on any hard error.

Hard errors (exit 1, every offending row printed — not just the first):
  * a `req` naming a course absent from the same program's course set
  * a cycle in the prerequisite graph (the cycle is printed)
  * an `anti` declared on one side only
  * a requirement whose explicit/any_of matcher names a missing course
  * a duplicate course code within one program (real rows)
  * `t` outside the range of that program's terms (−1 unscheduled is allowed)
  * a ghost row with no corresponding real course

Warnings (printed with a count, do not affect exit code):
  * needs_review: true courses
  * courses reachable from no requirement
  * offering: UNKNOWN

Depends on Stage 1 (`app.graph`) for cycle detection and Stage 2 (`app.catalog`)
for loading. Run: `python scripts/validate_catalog.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import graph  # noqa: E402
from app.catalog import Catalog, CatalogError, DATA_DIR, load_file  # noqa: E402


class Report:
    """Collects hard errors and warnings for one program."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


# --------------------------------------------------------------------------- #
# hard-error checks
# --------------------------------------------------------------------------- #

def _known_codes(rows: list[dict]) -> set[str]:
    """Codes that can satisfy a prerequisite: real (non-ghost) rows only."""
    return {r["c"] for r in rows if not r.get("ghost")}


def check_dangling_reqs(rows: list[dict], rep: Report) -> None:
    known = _known_codes(rows)
    for r in rows:
        if r.get("ghost"):
            continue
        for prereq in r.get("req", []):
            if prereq not in known:
                rep.error(
                    f"{r['c']} (term {r['t']}) requires {prereq!r}, "
                    f"which is not a course in this program"
                )


def check_cycle(rows: list[dict], rep: Report) -> None:
    # Run the Stage-1 graph closure from every node; the first cycle it names is
    # reported. graph.unlocks raises CatalogError naming the cycle.
    seen_cycles: set[str] = set()
    for r in rows:
        if r.get("ghost"):
            continue
        try:
            graph.unlocks(rows, r["c"])
        except graph.CatalogError as e:
            msg = str(e)
            if msg not in seen_cycles:
                seen_cycles.add(msg)
                rep.error(msg)


def check_one_sided_anti(rows: list[dict], rep: Report) -> None:
    anti_by: dict[str, set[str]] = {}
    for r in rows:
        if r.get("ghost"):
            continue
        anti_by.setdefault(r["c"], set()).update(r.get("anti", []))
    known = _known_codes(rows)
    reported: set[tuple[str, str]] = set()
    for a, antis in anti_by.items():
        for b in antis:
            if b not in known:
                continue  # absent target is a dangling-anti, covered elsewhere in spirit
            if a not in anti_by.get(b, set()):
                pair = tuple(sorted((a, b)))
                if pair not in reported:
                    reported.add(pair)
                    rep.error(
                        f"anti-requisite declared one side only: {a} lists {b}, "
                        f"but {b} does not list {a}"
                    )


def check_requirement_targets(cat: Catalog, rep: Report) -> None:
    known = set(cat.courses) | {g.code for g in cat.ghosts}
    for req in cat.requirements:
        for code in req.named_codes:
            if code not in known:
                rep.error(
                    f"requirement {req.id!r} names {code!r}, "
                    f"which is not a course in this program"
                )


def check_duplicate_codes(rows: list[dict], rep: Report) -> None:
    counts: dict[str, int] = {}
    for r in rows:
        if r.get("ghost"):
            continue
        counts[r["c"]] = counts.get(r["c"], 0) + 1
    for code, n in sorted(counts.items()):
        if n > 1:
            rep.error(f"duplicate course code {code!r} appears {n} times (real rows)")


def check_term_range(cat: Catalog, rep: Report) -> None:
    n = len(cat.terms)
    for r in cat.rows:
        t = r["t"]
        if t == -1:
            continue  # unscheduled is allowed
        if not (0 <= t < n):
            rep.error(
                f"{r['c']} has term index {t}, outside 0..{n - 1} "
                f"({'ghost' if r.get('ghost') else 'row'})"
            )


def check_ghost_has_real(cat: Catalog, rep: Report) -> None:
    for g in cat.ghosts:
        if g.code not in cat.courses:
            rep.error(
                f"ghost row {g.code!r} (term {g.term}) has no corresponding "
                f"real course"
            )


# --------------------------------------------------------------------------- #
# warning checks
# --------------------------------------------------------------------------- #

def check_needs_review(cat: Catalog, rep: Report) -> None:
    for c in sorted(cat.courses.values(), key=lambda c: c.code):
        if c.needs_review:
            note = f" — {c.review_note}" if c.review_note else ""
            rep.warn(f"needs_review: {c.code}{note}")


def check_unreachable(cat: Catalog, rep: Report) -> None:
    covered: set[str] = set()
    for req in cat.requirements:
        covered.update(req.named_codes)
    for c in sorted(cat.courses.values(), key=lambda c: c.code):
        if c.is_alt:
            continue  # alternatives are intentionally off the requirement lists
        if c.code not in covered:
            rep.warn(f"reachable from no requirement: {c.code} ({c.name})")


def check_offering_unknown(cat: Catalog, rep: Report) -> None:
    for c in sorted(cat.courses.values(), key=lambda c: c.code):
        if c.offering == "UNKNOWN":
            rep.warn(f"offering UNKNOWN: {c.code} ({c.name})")


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def validate(cat: Catalog) -> Report:
    rep = Report(f"{cat.school} · {cat.program.name} [{cat.program.id}]")
    rows = list(cat.rows)
    check_dangling_reqs(rows, rep)
    check_cycle(rows, rep)
    check_one_sided_anti(rows, rep)
    check_requirement_targets(cat, rep)
    check_duplicate_codes(rows, rep)
    check_term_range(cat, rep)
    check_ghost_has_real(cat, rep)
    check_needs_review(cat, rep)
    check_unreachable(cat, rep)
    check_offering_unknown(cat, rep)
    return rep


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]] or sorted(DATA_DIR.glob("*.json"))
    if not paths:
        print(f"no seed files found in {DATA_DIR}", file=sys.stderr)
        return 2

    total_errors = 0
    for path in paths:
        try:
            cat = load_file(path)
        except CatalogError as e:
            print(f"\n=== {path.name} ===")
            print(f"  HARD ERROR: could not load — {e}")
            total_errors += 1
            continue

        rep = validate(cat)
        print(f"\n=== {rep.label} ===")
        print(f"  {path.name}: {len(cat.courses)} courses, "
              f"{len(cat.ghosts)} ghost, {len(cat.requirements)} requirements, "
              f"{len(cat.terms)} terms")

        if rep.errors:
            print(f"  HARD ERRORS ({len(rep.errors)}):")
            for e in rep.errors:
                print(f"    ✗ {e}")
        else:
            print("  HARD ERRORS: none")

        if rep.warnings:
            print(f"  WARNINGS ({len(rep.warnings)}):")
            for w in rep.warnings:
                print(f"    ⚠ {w}")
        else:
            print("  WARNINGS: none")

        total_errors += len(rep.errors)

    print()
    if total_errors:
        print(f"FAILED: {total_errors} hard error(s) across {len(paths)} file(s).")
        return 1
    print(f"OK: {len(paths)} file(s) valid (warnings do not fail the build).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
