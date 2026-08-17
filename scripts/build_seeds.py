#!/usr/bin/env python3
"""Derive per-program seed JSON from the app's SCHOOLS datasets.

`school_datasets.js` never existed in this repo; the authoritative course data
lives in the SCHOOLS object inside `Compass Planner.html`. This script reads the
already-extracted nyu-cs / cmu-cs dump (scripts produce it via extract_schools.js)
and writes one seed file per program in the Stage-2 schema:

    { "school", "program", "terms", "requirements", "courses" }

Course rows keep the graph-compatible shape (c, n, cr, t, s, tier, req, anti,
plus ghost/alt/key/gen flags) so app.graph runs against them unchanged, and add
three catalog fields: `offering`, `needs_review`, `review_note`.

Requirement matchers (`explicit` / `any_of`) are authored here over the real
course codes — the app's display-oriented REQS carry no matcher, so this is the
one place the degree rules are written down. Everything else is copied verbatim.
"""
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = Path("/private/tmp/claude-501/-Users-alexzhong-stellic-pathfinders/"
           "aae4e2b0-bda1-4dd9-9aaa-1df4d3a44f00/scratchpad/schools_raw.json")

# Prereqs inferred from sample-sequence order rather than a published prerequisite.
# Carried as needs_review so the dataset can be corrected later (Stage-2 warning).
NEEDS_REVIEW = {
    "cmu-cs": {
        "15-259": "Prereq collapsed from CMU's OR-list (21-127 / 15-251 / 21-128 / "
                  "15-151) to the sample-sequence course; grades dropped.",
        "10-315": "Prerequisites inferred from sample-sequence order; program page "
                  "printed none.",
    },
    "nyu-cs": {},
}

# Courses whose term offering is genuinely not known (special topics, or the
# needs_review rows). Everything else gets a derived seasonal pattern.
OFFERING_UNKNOWN = {
    "nyu-cs": {"CSCI-UA 480"},          # "Special Topics" rotates
    "cmu-cs": {"15-259", "10-315"},     # inferred rows — offering unverified too
}

# Program identity + authored requirement matchers, per program.
PROGRAMS = {
    "nyu-cs": {
        "file": "nyu_bacs_2026.json",
        "id": "nyu-bacs-2026",
        "name": "Computer Science, B.A.",
        "degree": "BA",
        "catalog_year": "2026",
        "requirements": [
            {"id": "cs-required", "name": "Required computer science",
             "min_courses": 6, "match": {"explicit": [
                 "CSCI-UA 2", "CSCI-UA 101", "CSCI-UA 102",
                 "CSCI-UA 201", "CSCI-UA 202", "CSCI-UA 310"]}},
            {"id": "math-required", "name": "Required mathematics",
             "min_courses": 2, "match": {"explicit": ["MATH-UA 120", "MATH-UA 121"]}},
            {"id": "cs-electives", "name": "400-level CS electives",
             "min_courses": 5, "match": {"any_of": [
                 "CSCI-UA 453", "CSCI-UA 479", "CSCI-UA 473",
                 "CSCI-UA 467", "CSCI-UA 421", "CSCI-UA 480"]}},
            {"id": "college-core", "name": "College Core Curriculum",
             "min_courses": 6, "match": {"any_of": [
                 "EXPOS-UA 1", "FYSEM-UA 1", "CORE-UA 401", "CORE-UA 550",
                 "CORE-UA 710", "CORE-UA 201", "CORE-UA 301", "CORE-UA 610"]}},
            {"id": "language", "name": "Foreign language",
             "min_courses": 4, "match": {"any_of": [
                 "FREN-UA 1", "FREN-UA 2", "FREN-UA 11"]}},
        ],
    },
    "cmu-cs": {
        "file": "cmu_bscs_2025.json",
        "id": "cmu-bscs-2025",
        "name": "Computer Science, B.S.",
        "degree": "BS",
        "catalog_year": "2025",
        "requirements": [
            {"id": "cs-core", "name": "Computer science core",
             "min_courses": 5, "match": {"explicit": [
                 "15-122", "15-150", "15-210", "15-213", "15-251"]}},
            {"id": "cs-electives", "name": "CS electives",
             "min_courses": 4, "match": {"any_of": [
                 "15-451", "15-410", "15-411", "15-455", "15-462", "10-315"]}},
            {"id": "math-core", "name": "Mathematics",
             "min_courses": 4, "match": {"explicit": [
                 "21-120", "21-122", "21-127", "21-241"]}},
            {"id": "probability", "name": "Probability",
             "min_courses": 1, "match": {"any_of": ["15-259", "36-218"]}},
            {"id": "science", "name": "Science & engineering",
             "min_courses": 2, "match": {"any_of": ["33-121", "09-105"]}},
            {"id": "humanities", "name": "Humanities & arts",
             "min_courses": 3, "match": {"any_of": [
                 "76-101", "76-270", "79-104", "73-102"]}},
        ],
    },
}

# Derived seasonal offering, mirroring the app's offeringOf() rule.
def offering_of(code: str, tier) -> str:
    m = "".join(ch for ch in code if ch.isdigit())
    lvl = 100
    if m:
        n = int(m[-4:]) if len(m) >= 4 else int(m)
        lvl = (n // 1000 * 100) if n >= 1000 else (n // 100 * 100 or 100)
    h = 5
    for ch in code:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    if lvl <= 100 or tier == 0:
        return "Summer · Fall · Spring"
    if lvl >= 400 or tier == 4:
        return "Fall" if h % 2 else "Spring"
    return ("Fall" if (h >> 1) % 2 else "Spring") if h % 4 == 0 else "Fall · Spring"


def build(pid: str, raw: dict) -> dict:
    P = PROGRAMS[pid]
    meta = raw["META"]
    reviews = NEEDS_REVIEW.get(pid, {})
    unknown = OFFERING_UNKNOWN.get(pid, set())

    courses = []
    for c in raw["COURSES"]:
        row = {
            "c": c["c"], "n": c["n"], "cr": c["cr"], "t": c["t"], "s": c["s"],
        }
        for opt in ("tier", "req", "anti", "gen", "key", "alt", "ghost", "note", "g"):
            if opt in c:
                row[opt] = c[opt]
        code = c["c"]
        row["offering"] = "UNKNOWN" if code in unknown else offering_of(code, c.get("tier"))
        row["needs_review"] = code in reviews
        row["review_note"] = reviews.get(code)
        courses.append(row)

    return {
        "school": meta["school"],
        "program": {
            "id": P["id"], "name": P["name"], "degree": P["degree"],
            "catalog_year": P["catalog_year"],
            "unit_label": meta["unitLabel"], "unit_abbr": meta["unitAbbr"],
            "total_units": meta["totalCr"],
        },
        "terms": [
            {"index": i, "key": t["k"], "label": t["l"], "tag": t.get("tag", ""),
             "status": t.get("st", "")}
            for i, t in enumerate(raw["TERMS"])
        ],
        "requirements": P["requirements"],
        "courses": courses,
    }


def main() -> None:
    raw = json.loads(RAW.read_text())
    (ROOT / "data").mkdir(exist_ok=True)
    for pid, P in PROGRAMS.items():
        seed = build(pid, raw[pid])
        out = ROOT / "data" / P["file"]
        io.open(out, "w", encoding="utf-8").write(json.dumps(seed, indent=2) + "\n")
        print(f"wrote {out.relative_to(ROOT)}  ({len(seed['courses'])} courses, "
              f"{len(seed['requirements'])} requirements)")


if __name__ == "__main__":
    main()
