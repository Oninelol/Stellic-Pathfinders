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

## Phase 3 — Stateless evaluation ✅ (complete)

**Built.** `POST /programs/{id}/evaluate` — body `{"edits": {moved, added, removed}}`,
response `{blocked, conflicts, totals, key_course, groups, unknown_codes}`.
The client posts *edits*, not a reconstructed plan; the server applies them with
`plan.apply_edits`. Statuses are recomputed by `graph.status_for`, so a moved course
reflects its new term rather than the seed's baked status. Assembly lives in
`schemas.evaluate_edits()` — the ONE evaluation code path, shared with
`GET /me/plans/{id}/evaluate` so the two can never diverge.

**Acceptance.** Empty edits reproduce every seed's derived groups/totals/key for all
nine ✅ · moving a course before its prereq blocks it with the right codes and moving
back clears it ✅ · unknown codes land in `unknown_codes` with a 200 (a transfer credit
gets an answer, not a 422) ✅ · out-of-range term → 422 naming `0..7` ✅ · stateless and
repeatable, no residue between calls ✅ · conflicts surface at plan level ✅.

**⚠ Real data defect found by /evaluate (reported, NOT silently fixed).**
Two published curricula schedule a course in the SAME term as its prerequisite:
- `nyu-me`: **ME-UY 2223 Dynamics** (term 4) requires **ME-UY 2213 Statics** (term 4)
- `nyu-enve`: **CE-UY 2253 Hydrology** (term 4) requires **CE-UY 2213 Fluid Mechanics** (term 4)

The computed result (blocked) is correct; the authored course placement in
`scripts/curricula.py` is what is wrong. Fixing it means moving the dependent course
to term 5 — a data change that shifts that program's credit distribution, so it is
left for a decision rather than silently applied. Recorded in
`tests/test_evaluate.py::KNOWN_SAME_TERM_DEFECTS`; the other seven are clean.

---

## Phase 3.5/3.6 (adapted) — Accounts and per-user data ✅ (complete)

**Deviation from the original plan, on explicit instruction.** The plan said "use Clerk
or Supabase; do not roll your own". The user asked for a self-hosted sign-up/login, so
this is email + password built on standard primitives rather than hand-rolled crypto:
`hashlib.scrypt` (stdlib, memory-hard) with a per-user 16-byte salt and
`hmac.compare_digest`; stateless HS256 JWTs via PyJWT. No plaintext is ever stored.

**Built.**
- `app/db.py` (SQLite engine + session dep, FK pragma on), `app/models.py`
  (User, Plan, PlanEntry), `app/auth.py` (hashing, tokens, `current_user`/`optional_user`),
  `app/routes_user.py` (auth + plans), `alembic/` with `0001_users` → `0002_user_data`.
- Endpoints: `POST /auth/signup`, `POST /auth/login`, `GET /me`,
  `POST /auth/logout-everywhere`, `GET|POST /me/plans`,
  `GET|PATCH|DELETE /me/plans/{id}`, `PUT /me/plans/{id}/entries`,
  `PATCH /me/plans/{id}/entries/{code}`, `GET /me/plans/{id}/evaluate`.
- **Stay signed in** is the token lifetime, not a second mechanism: 12h normally,
  90 days with `remember`. The client keeps it in `localStorage` when remembered and
  `sessionStorage` otherwise, and `restoreSession()` auto-logs-in on load.
- Frontend: sign-in/sign-up modal, sidebar account block with SYNCED badge + sign out,
  debounced (600ms) plan push, server-first restore on login.

**Acceptance.** Signup→`/me` works and reuses the row ✅ · no token vs malformed token
are distinguishable 401s (`no_token` / `token_invalid` / `token_expired` /
`token_revoked`) ✅ · every catalog + evaluate endpoint still works with no
Authorization header (asserted by name in `test_catalog_and_evaluate_stay_public`) ✅ ·
tests run with no network ✅ · `alembic upgrade 0001_users` creates only `users`;
`upgrade head` adds plans/plan_entries; `downgrade 0001_users` leaves users intact;
`downgrade base` reverses cleanly ✅ · another user's plan is **404, not 403**, on every
endpoint ✅ · delete cascades with no orphans ✅ · second primary unsets the first ✅ ·
unknown course saves and surfaces in `unknown_codes` ✅ · grades round-trip with basis ✅ ·
`GET /me/plans/{id}/evaluate` == `POST /programs/{id}/evaluate` for the same entries ✅.

**Verified in-browser (fresh DB):** signed up `maya@nyu.edu` → token in localStorage →
added CSCI-UA 480 → server stored 28 entries → cleared the local plan cache and
reloaded → still signed in and the plan **restored from the server** at Spring 2027 →
second account `jordan@cmu.edu` saw **0 plans** (isolated) → signing back in as maya
returned her plan → wrong password 401.

**Deferred.** Profile/goals/wins tables and the localStorage→server import prompt
(the remaining 3.6 surface); Phase 4 audit; Phase 5 planner. `grade`/`grading_basis`
columns exist and round-trip, unused until Phase 4.

---

## Accounts: school + major at sign-up, profile in the header ✅

**Built.**
- **Sign-up captures the student's school + major.** `POST /auth/signup` accepts an
  optional `program_id`, validated against the seed catalog (422 listing known ids if
  unknown). It is stored on `users.program_id` (migration `0003_user_program`) — a
  plain string, never a foreign key, since the catalog lives in seed JSON. On sign-up
  the account also gets a **primary plan** for that program, so their data has
  somewhere to live from the first edit.
- **`/me`, signup and login now return `program_id` and derived `initials`** (two
  letters from the display name, else the email local part).
- **Home header is the auth surface.** The old SCHOOL & MAJOR select in the top right
  is replaced by **Log in / Sign up** when signed out, and by a **profile pill**
  (initials + email + SYNCED, click for a menu with Sign out) when signed in. Program
  switching still lives in the sidebar selector, so nothing was lost.
- **The sign-up form** gained a grouped "YOUR SCHOOL & MAJOR" dropdown (login does not
  show it). On success the app adopts that program, so the board opens on their major.
- **Identity follows the account**: the greeting, the big avatar and the sidebar name
  use the signed-in user (falling back to the demo persona when anonymous).

**Verified in-browser (fresh database).** Sign up as `jordan.kim@cmu.edu` choosing CMU
Mechanical Engineering → modal closes, header shows `JK` + SYNCED, greeting reads
"Welcome back, Jordan", the board switches to cmu-me and reports **units**. Reload →
still signed in, program restored. Account menu → Sign out → Log in / Sign up return
and the demo persona comes back. Log back in → `JK`, cmu-me, synced.

**Bug found and fixed: the test suite was writing into the dev database.** `app.db`
reads `DATABASE_URL` at import time, and `test_auth.py` set it *after* `test_api.py`
had already imported the app — so in a full-suite run the auth tests hit the real
`compass.db` (23 stray users accumulated there). `DATABASE_URL` now points at a
throwaway file from `conftest.py`, before any `app.*` import. Confirmed: a full run
leaves `compass.db` empty, and the suite is repeatable.

**Tests.** 155 passed (was 151; +4 covering program capture, the auto-created primary
plan, unknown-program rejection, and initials on login).

---

## Login gate + student identity from the account ✅

**Built.**
- **The app is gated.** A full-screen login page is the first thing rendered; nothing
  else is usable until a user signs in. `authGate` is `!user && !sessionChecking`, and
  `sessionChecking` is seeded from a stored token at construction, so a returning user
  never sees the gate flash before `/me` answers.
- **Sign-up asks for the name first.** Two steps: *"Tell us your name"* (first + last,
  validated — Continue refuses an empty name) → *"Create your account"* (username/email,
  password, school & major, keep-me-signed-in), with a Back link. Log-in shows only
  username and password.
- **Names are stored** (`users.first_name` / `last_name`, migration `0004_user_names`).
  `_user_out` returns `first_name`, `last_name`, `full_name` and derives `initials`
  from the real name (`Ada Lovelace` → `AL`), falling back to the email local part when
  no name was given.
- **Student information comes from the account only.** The greeting, the large Home
  avatar, the sidebar avatar and the sidebar name all read the signed-in user; the
  hard-coded "Maya Okonkwo" / "MO" demo persona is gone (empty when there is no user).

**Verified in-browser.** Fresh state → login page alone (only *Username or email* and
*Password*). Create an account → step 1 name (blocks empty), step 2 credentials +
program → lands signed in as **Priya Raman**, initials `PR`, greeting "Welcome back,
Priya", board on **nyu-cbe** reporting credits. Reload → still signed in, no gate
flash, program restored. Sign out → gate returns, token cleared.

**Bug caught during testing:** the running uvicorn still held pre-migration code, so
the first UI sign-up returned no `full_name` and ignored the chosen program. Restarting
the API fixed it — worth remembering that `make run` must be restarted after backend
edits (`make api` runs with `--reload`).

**Tests.** 158 passed (+3: name capture, `/me` identity block, optional-name fallback).
`alembic downgrade 0003_user_program` and back up verified clean.

---

## Settings panel ✅

**Built.** A **Settings** entry in the top-right account menu opens a panel with four
sections, all backed by real endpoints.

- **Profile picture.** Choose an image → the client centre-crops and downscales it to a
  256px JPEG before upload, so the row and every `/me` response stay small. Stored as a
  data: URL on `users.avatar` (migration `0005_user_settings`); `PATCH /me/profile`
  rejects non-images (422) and anything over ~300 KB (413), and `""` clears it. The
  picture replaces the initials **everywhere** they appeared — sidebar (32px), Home
  header (66px), account pill (34px) and the settings preview.
- **School & major.** Grouped select; validated server-side (422 listing known ids).
  Saving switches the whole app to that program.
- **Year of graduation.** Stored on `users.grad_year` (range-checked 1950–2100) and
  overrides the program default wherever the term is shown — "Class of 2031" on Home
  and "Spring 2031 · projected graduation" on Overview, via one `effGradTerm()` helper.
- **Change password.** Requires the current password (403 if wrong), enforces the same
  strength rule as sign-up (422), and **bumps `token_version`** so existing tokens stop
  verifying; the client then signs out and asks for the new password.

**Two real bugs found and fixed while testing.**
1. *Data URL truncated in CSS.* The avatar was first applied as
   `background-image:url(<data-url>)` in a style **string**. The runtime turns style
   strings into objects by splitting on `;` and `:` — which a data: URL is full of — so
   the value arrived as `url("data:image/png")` and nothing rendered. Quoting did not
   help; the picture is now an `<img src>` (attribute, not CSS) with the circle styling
   on the element, and all sites render.
2. *Graduation year saved but not shown.* `grad_year` reached the database while the UI
   still read the program's `META.gradTerm`. Added `effGradTerm()` and routed the two
   display sites plus `homeSub` through it.

**Verified in-browser.** Uploaded a picture → appears in all four places, persists over
sign-out/in. Changed program cmu-me → nyu-ee (sidebar reads ELECTRICAL ENG BS · TANDON)
and year 2029 → 2031 (Class of 2031, Spring 2031 projected). Wrong current password
refused; correct one succeeded, session revoked, new password signs in and avatar,
program and year are all still there.

**Tests.** 165 passed (+7 covering profile update, validation, avatar set/clear/limits,
password change with revocation, weak-password rejection, and auth on both endpoints).
`alembic downgrade 0004_user_names` and back up verified clean.

---

## Per-user isolation audit ✅

**What was tested.** Two accounts (Alice/nyu-cs, Bob/cmu-me), against both the
TestClient and the live server, plus the real browser UI.

- **Positive half:** each account's plans, entries, profile, program, graduation year
  and identity are its own and differ; plan ids never overlap; one user's profile edit
  does not appear on the other.
- **Negative half:** every id-scoped route (`GET/PATCH/DELETE /me/plans/{id}`,
  `PUT .../entries`, `PATCH .../entries/{code}`, `GET .../evaluate`) returns **404 —
  never 403** — for a non-owner, and the owner's data is byte-identical afterwards.
  Plan-id enumeration over a range only ever returns the caller's own rows.
- **Credentials:** every `/me*` route is 401 without a token and 401 with a garbage
  token; a token forged with the wrong signing key is rejected; a password change
  revokes only that user's sessions (the other stays signed in); `logout-everywhere`
  is scoped to the caller.
- **Structural guard:** a test walks the live route table and asserts every registered
  `/me*` method rejects an unauthenticated request, so a future endpoint that forgets
  the `current_user` dependency fails in CI rather than in production.

Server-side scoping is centralised in `_own_plan(plan_id, user, db)` — every id-route
goes through it, which is why the surface is uniform.

**One real leak found — client-side, now fixed.** The API never leaked, but the bundle
did: `signOut` left `state.edits` and its localStorage copy in place, and
`syncPlansFromServer` *merged* the incoming user's plans onto whatever was already
there. Signing in as Bob on a device Alice had used showed Alice's edits for any
program Bob had no plan for. Reproduced in the browser (ECE-UY 3604 sitting in Spring
2025 instead of its published Fall 2027 under Bob's account), then fixed: sign-out
clears the edits in memory and in storage, and sign-in **replaces** rather than merges.
Re-verified both directions in the browser, with a regression guard asserted against
the shipped bundle.

**Note:** because there is no localStorage→server import flow yet, edits made while
signed out are discarded on sign-in rather than merged. That is the safe side of the
trade; an explicit, one-way import is the follow-up.

**Tests.** 201 passed (+36: `tests/test_isolation.py`).

---

## Account database audit ✅

**Confirmed: a real database manages sign-up/log-in, and all per-user data is linked
to the account by foreign key.** SQLite via SQLAlchemy + Alembic (five migrations);
one connection-string change moves it to Postgres.

```
users                                  <- sign-up / log-in
  id PK, email UNIQUE NOT NULL (indexed), password_hash NOT NULL,
  token_version, display_name, first_name, last_name,
  program_id, grad_year, avatar, created_at

plans          user_id  -> users.id  ON DELETE CASCADE   (indexed)
plan_entries   plan_id  -> plans.id  ON DELETE CASCADE   (indexed)
               UNIQUE (plan_id, course_code)
```

**Verified against the live database (not just the code).**
- Passwords are **scrypt hashes with a per-user salt**; grepping the .db file for the
  plaintext passwords returns 0 hits, and two accounts sharing a password get
  different hashes.
- A second account on the same email is refused by the DB (`UNIQUE constraint failed:
  users.email`), independently of any API check.
- **Foreign keys are enforced.** SQLite ignores `ON DELETE CASCADE` unless
  `PRAGMA foreign_keys=ON`; `app/db.py` sets it on every connect, and the pragma is now
  asserted in a test — without it the cascades would be silently dead.
- An orphan plan or entry is rejected (`FOREIGN KEY constraint failed`), and deleting a
  user row *directly in SQL* removes their plans and entries while the other account's
  rows stay intact.
- Every row joins back to an owner: 0 plans without a user, 0 entries without a plan.
- No catalog table exists — course data stays in seed JSON, so "reload the catalog"
  never touches user data.

**One divergence found and fixed.** `users.display_name` was NOT NULL in the SQLAlchemy
model but nullable in migration `0001`, so the test database (built by `create_all`)
and the production database (built by Alembic) disagreed. Alembic is what production
runs, so the model was aligned to it. This is exactly the kind of drift that only
surfaces as a production-only insert failure.

**Tests.** 211 passed (+10: `tests/test_db_integrity.py`, which asserts the
*database's* guarantees rather than the API's behaviour). Migrations verified to
round-trip `base` → `head`.

---

## Fix: school/major picker unresponsive on sign-up ✅

**Symptom.** On the sign-up form the school & major dropdown did not react to clicks.

**Cause — two bugs, both about the catalog not being loaded.**
1. The login gate renders immediately, but the program list comes from `GET /schools`.
   If that request had not returned (API down, slow start, cold start), the picker
   rendered with **zero options** — a control that opens nothing and explains nothing.
2. The "Can't reach the catalog" screen was `z-index: 200`, *below* the login gate at
   `z-index: 400`. So a user whose API was unreachable saw a normal-looking login page
   with a dead dropdown and **no error at all** — the explanation was rendered but
   covered.

The dropdown itself was never broken: with options present, clicking focuses it,
nothing calls `preventDefault` on mousedown, the node is not replaced mid-interaction,
and a selection sticks through the re-render. Verified all four directly.

**Fix.**
- Catalog error overlay raised to `z-index: 420`, above the gate — a failure is now
  always visible.
- The picker renders only when programs exist. Otherwise an inline notice takes its
  place: *"Loading programs…"*, or *"Program list unavailable — the catalog service is
  not reachable."* with a **RETRY** button.
- Sign-up refuses to submit with no program list, with a specific message, instead of
  silently creating an account with no program.

**Verified.** API down → error screen with Retry (not a dead form). Retry with the API
back → gate returns, picker has all nine programs. Selecting `nyu-enve` sticks through
re-render and is the program the new account lands on (`Welcome back, Dana`, initials
`DF`, board on Environmental Engineering).

**Tests.** 212 passed (+1 regression guard asserting the fallback states, the submit
guard, and the z-order against the shipped bundle).

---
