# Compass Planner — build progress

One line per phase. Before starting a phase, read this file and `git log --oneline -5`.
Do not start a phase whose predecessor is incomplete.

---

## Phase 0 — Alignment ✅ (complete)

**Built.** Made `scripts/curricula.py` the single source of course data and split
generation into two thin emitters:

- `scripts/emit_frontend.py` — tuples → `SCHOOLS` block → `build/template.html`
- `scripts/emit_seeds.py` — tuples → `data/<id>.json`, one file per program

Nine seed files now exist (`nyu-cs, nyu-me, nyu-ce, nyu-cpe, nyu-ee, nyu-cbe,
nyu-enve, cmu-cs, cmu-me`). `scripts/build_seeds.py` deleted. Added `app/plan.py`
(`apply_edits`, `row_id`), `graph.status_for`, `catalog.Program` fields
(`tab, tiers, grad, year, key, keyname, headline, blurb, snapshot,
needs_requirements`), `catalog.Course.offering_source`, `Catalog.groups`. Extended
`validate_catalog.py` with four checks (key disagreement, bad `g`, needs_requirements,
derived offerings). New tests: `test_plan.py`, plus catalog cross-check /
mapping / determinism tests. `tests/fixtures/edit_plan.json` (JS-captured).

**Decisions.**
- **Program ids = the frontend keys** (`nyu-cs`, …). Identity mapping, no table.
  `catalog_year` kept as a field (NYU 2026, CMU 2025). Old ids `nyu-bacs-2026` /
  `cmu-bscs-2025` retired.
- **Requirements modelled twice, distinctly:** a derived `groups` section (reproduces
  the frontend REQS) on all nine; a `requirements` section with real matchers only on
  the two CS programs. The seven engineering programs get `requirements: []` and
  `needs_requirements: true`. No degree rules were invented.
- **Offerings:** all 258 real-course offerings are `offering_source: "derived"`
  (hash-fabricated); 0 are `"catalog"`. The validator warns per program.

**Acceptance — all verified.**
1. Both emitters run; running twice changes no bytes (`shasum` of `data/*.json` +
   `build/template.html` identical across two runs). ✅
2. `validate_catalog.py` covers 9 programs, per-program errors/warnings, exit 0. ✅
3. `catalog.load_all()` → 9; `schools()` nests CMU(2) + NYU(7). ✅
4. `graph.key_course()` runs on all nine without raising (`test_key_course_runs_on_all_nine`). ✅
5. Every frontend key → exactly one seed (`test_every_frontend_key_maps_to_exactly_one_seed`). ✅
6. Seed group counts == frontend REQS for all nine (`test_seed_groups_match_frontend_reqs`). ✅
7. `apply_edits` reproduces JS `get COURSES()` for move / no-op move / add / remove /
   ghost — pinned against node-captured output (`test_apply_edits_matches_js_fixture`). ✅
8. `build_seeds.py` gone, no references. ✅
9. No absolute paths outside the repo in `scripts/` or `app/`. ✅
10. `pytest` → 77 passed. ✅

**Disagreements (computed vs authored).**
- **Key course:** none. Authored `key` == `graph.key_course()` for all nine.
- **Credits:** the generic mock `tests/fixtures/default_plan.json` still pins the
  computed-**42** vs authored-**41** `done` case (left untouched per instruction; 42 is
  the correct sum of the data). The nine real seeds reconcile — `doneCr` is derived.

**Deferred / notes for Phase 1.**
- The bundled `Compass Planner.html` also carries earlier frontend feature work (Home /
  Career / Visa screens, editable plan, visa profiles) done before this plan; it is not
  part of Phase 0 and is committed alongside as frontend state. `emit_frontend` is
  byte-identical to the `SCHOOLS` block already in `build/template.html`, so Phase 0
  changed no rendered bytes.
- Phase 1 (read-only API) is next: `app/main.py`, `app/schemas.py`, `tests/test_api.py`,
  `requirements.txt`. Do NOT start it until this phase is committed.

---
