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

## Phase 1 — Read-only API ✅ (complete)

**Built.** FastAPI read-only service, thin shells over the pure modules.

- `app/schemas.py` — pydantic response models **and** the pure builders
  (`to_health/to_schools/to_coursemap/to_detail`). Endpoints call these, so no domain
  logic lives in a route body (purity contract).
- `app/main.py` — `GET /healthz`, `/schools`, `/programs/{id}/coursemap`,
  `/programs/{id}/courses/{code}`. Catalog warmed once at startup via lifespan
  (`load_all()` memoised, not defeated in a dependency). CORS = local dev origins only
  (`localhost`/`127.0.0.1`, GET only) — not `*` (Phase 6 sets the deployed origin).
- `requirements.txt` — pinned fastapi/uvicorn/pydantic/httpx/pytest.
- `tests/test_api.py` — 29 tests via `TestClient` (no network/server).

**`/coursemap` is self-contained** — the client holds no school-specific string.
Payload: program/school names, `unit_label`/`unit_abbr`, `tiers`, `terms`, `groups`,
`requirements`, `needs_requirements`, `meta` (`done_cr, in_prog_cr, pct, behind_cr,
grad_term, class_year, key_code, key_name, headline, blurb, snapshot`), `nodes`,
`edges`. Meta is **derived** at request time (credit sums from `graph.credit_totals`;
`pct = round(done/total*100)`; `behind_cr = key units + ghost units`), not read from
the seed. Nodes carry `offering_source`; edges carry `kind ∈ {prereq, anti}`.

**Acceptance — all verified.**
1. Boots (uvicorn + TestClient) and `/healthz` reports `programs: 9, courses: 267`. ✅
2. `/schools` returns all nine nested (CMU 2, NYU 7) in one call. ✅
3. All nine coursemaps complete (`test_coursemap_complete`); NYU→`credits`, CMU→`units`
   (`test_nyu_credits_cmu_units`). ✅
4. Detail matches `graph.blocked_by` / `direct_unlocks` / `unlocks` spot-checked per
   program (`test_detail_matches_graph`, parametrised over nine). ✅
5. Unknown program → 404 with `known_programs`; unknown course → 404 naming the program
   with `known_courses`. ✅
6. Response shape identical across all nine — one top-level/meta/node/edge key set,
   no program-specific keys (`test_shape_identical_across_all_nine`). ✅
7. `pytest` → 106 passed (77 prior + 29 API). ✅
8. Anonymous works end to end — every endpoint responds with no `Authorization` header
   (verified by curl and the whole test suite, which never sends one). ✅

**Notes for the next phase.**
- No blocked *real* courses in any published plan (the ghost is separate), so
  `blocked_by` is `[]` in every coursemap detail — blocking only appears under edits,
  which is Phase 3 (`/evaluate`).
- Frontend untouched, as required. Phase 2 is next: make the bundle fetch `/schools`
  and `/coursemap` (adapter into the existing META/TERMS/COURSES shape) and persist
  edits to `localStorage`. After Phase 2, `curricula.py` writes seeds only.

---

## Phase 2 — Frontend fetches + plans persist ✅ (complete)

**Built.**
- **Fetch.** The bundle's inlined `SCHOOLS = {…}` is gone; `get SCHOOLS()` reads
  `state.fetched`. On mount it `GET`s `/schools` (builds the selector) then every
  program's `/coursemap`. One marked `adaptCoursemap()` maps the payload into the
  existing `META/TERMS/REQS/TIERS/COURSES` shape — `boardVals`, `detailFor`, `FINDER`,
  `PATHS` are unchanged. A `LOADING_SHAPE` placeholder keeps `renderVals()` from
  throwing before data arrives; a full-screen loading overlay covers it, and an API
  error shows a readable screen with **Retry** (not a blank page).
- **API additions (needed so the client holds no school-specific string):** coursemap
  `+ program` (the `CS BA · COURANT` descriptor) `+ tab`; nodes `+ req/anti/note`;
  `/schools` program summary `+ tab`; seed/`catalog.Program` `+ descriptor`.
- **Persistence.** `state.edits` → `localStorage` under `compass.edits.v1` (schema
  versioned). Written on every `writeEdits` **and** `resetPlan`; restored on mount
  before the board renders; stale entries (course gone from catalog) pruned on load,
  never crash. Every `localStorage` call is try/catch'd.
- **Two writers reconciled.** `emit_frontend.py` deleted; `curricula.py` writes seeds
  only (via `emit_seeds`). The bundle no longer carries a `SCHOOLS` block.

**Acceptance — all verified in-browser (API on :8000, bundle on :8793).**
1. All nine render from the API (fetched `/schools` + 9 coursemaps; selector shows
   nine; engineering programs render real nodes). ✅
2. Switching programs redraws without remounting (CMU→`units`, Class 2028). ✅
3. Edits survive reload (added `15-455`→Spring 2027 persisted through a reload). ✅
4. Reset clears one program only (reset nyu-cs kept cmu-cs in localStorage). ✅
5. API down → readable error + Retry; Retry recovers all nine. ✅
6. `localStorage` throwing on read+write → app still boots and edits still apply
   (just not persisted); no crash. ✅
7. `rebuild.py verify` passes; `pytest` 106 passed. ✅

**Notes / fixes.**
- Found and fixed a bug mid-phase: `resetPlan` cleared in-memory state but not
  `localStorage`, so a reset edit came back on reload. Now persists.
- `API_BASE` defaults to `http://localhost:8000`, overridable via
  `window.COMPASS_API_BASE` (Phase 6 wires it from env). CORS already allows any
  localhost origin.
- Frontend files: `Compass Planner.html` is committed; `build/template.html` stays
  untracked scratch (regenerate via `rebuild.py extract`).
- Phase 3 next: `POST /programs/{id}/evaluate` (stateless), and the frontend replaces
  its client-side `UNMET` with a debounced POST — keep the client fn behind a flag to
  cross-check during dev.

---
