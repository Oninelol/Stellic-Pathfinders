"""Per-user data isolation.

Two users, two different plans. Every user-scoped endpoint is exercised from the
wrong account and must behave as if the resource does not exist. Also asserts the
positive half — each user's own data syncs back to them intact and independently.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_n = {"i": 0}


def make_user(program_id="nyu-cs", first="Test", last="User", password="hunter2hunter2"):
    """A fresh account with its own auth header."""
    _n["i"] += 1
    email = f"iso{_n['i']}@example.edu"
    r = client.post("/auth/signup", json={
        "email": email, "password": password, "first_name": first,
        "last_name": last, "program_id": program_id})
    assert r.status_code == 201, r.text
    body = r.json()
    return {
        "email": email, "password": password, "user": body["user"],
        "h": {"Authorization": f"Bearer {body['token']}"},
    }


@pytest.fixture
def alice():
    return make_user(program_id="nyu-cs", first="Alice", last="Ng")


@pytest.fixture
def bob():
    return make_user(program_id="cmu-me", first="Bob", last="Ortiz")


def plan_of(u, program_id, name, entries):
    """Create a plan with entries for user ``u`` and return it."""
    p = client.post("/me/plans", headers=u["h"],
                    json={"program_id": program_id, "name": name}).json()
    r = client.put(f"/me/plans/{p['id']}/entries", headers=u["h"], json=entries)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# the positive half: each user's own data is theirs, and differs
# --------------------------------------------------------------------------- #

def test_two_users_hold_independent_data(alice, bob):
    a = plan_of(alice, "nyu-cs", "Alice's plan",
                [{"course_code": "CSCI-UA 102", "term": 2, "status": "COMPLETE", "grade": "A"}])
    b = plan_of(bob, "cmu-me", "Bob's plan",
                [{"course_code": "24-101", "term": 1, "status": "PLANNED"}])

    a_seen = client.get("/me/plans", headers=alice["h"]).json()
    b_seen = client.get("/me/plans", headers=bob["h"]).json()

    # each sees only their own plans
    assert {p["name"] for p in a_seen} == {"My plan", "Alice's plan"}
    assert {p["name"] for p in b_seen} == {"My plan", "Bob's plan"}
    assert {p["id"] for p in a_seen}.isdisjoint({p["id"] for p in b_seen})

    # and the contents are genuinely different
    a_codes = {e["course_code"] for e in client.get(
        f"/me/plans/{a['id']}", headers=alice["h"]).json()["entries"]}
    b_codes = {e["course_code"] for e in client.get(
        f"/me/plans/{b['id']}", headers=bob["h"]).json()["entries"]}
    assert a_codes == {"CSCI-UA 102"} and b_codes == {"24-101"}


def test_profiles_are_independent(alice, bob):
    assert alice["user"]["program_id"] == "nyu-cs"
    assert bob["user"]["program_id"] == "cmu-me"
    assert alice["user"]["initials"] == "AN" and bob["user"]["initials"] == "BO"

    client.patch("/me/profile", headers=alice["h"], json={"grad_year": 2030})
    # Bob is untouched by Alice's change
    assert client.get("/me", headers=bob["h"]).json()["grad_year"] is None
    assert client.get("/me", headers=alice["h"]).json()["grad_year"] == 2030


def test_each_user_sees_their_own_identity(alice, bob):
    assert client.get("/me", headers=alice["h"]).json()["full_name"] == "Alice Ng"
    assert client.get("/me", headers=bob["h"]).json()["full_name"] == "Bob Ortiz"


# --------------------------------------------------------------------------- #
# the negative half: another user's resources are invisible
# --------------------------------------------------------------------------- #

def test_every_plan_endpoint_404s_for_a_non_owner(alice, bob):
    a = plan_of(alice, "nyu-cs", "Alice's plan",
                [{"course_code": "CSCI-UA 102", "term": 2}])
    pid = a["id"]
    # Bob attempts every id-scoped route against Alice's plan
    attempts = [
        ("GET",    f"/me/plans/{pid}",                        None),
        ("PATCH",  f"/me/plans/{pid}",                        {"name": "pwned"}),
        ("DELETE", f"/me/plans/{pid}",                        None),
        ("PUT",    f"/me/plans/{pid}/entries",                []),
        ("PATCH",  f"/me/plans/{pid}/entries/CSCI-UA 102",    {"term": 7}),
        ("GET",    f"/me/plans/{pid}/evaluate",               None),
    ]
    for method, url, body in attempts:
        r = client.request(method, url, headers=bob["h"], json=body)
        # 404, never 403 — do not confirm that someone else's resource exists
        assert r.status_code == 404, f"{method} {url} -> {r.status_code}"

    # Alice's plan is untouched by every one of those attempts
    still = client.get(f"/me/plans/{pid}", headers=alice["h"]).json()
    assert still["name"] == "Alice's plan"
    assert [e["course_code"] for e in still["entries"]] == ["CSCI-UA 102"]
    assert still["entries"][0]["term"] == 2


def test_non_owner_cannot_delete(alice, bob):
    a = plan_of(alice, "nyu-cs", "Keep me", [{"course_code": "CSCI-UA 102", "term": 2}])
    assert client.delete(f"/me/plans/{a['id']}", headers=bob["h"]).status_code == 404
    assert client.get(f"/me/plans/{a['id']}", headers=alice["h"]).status_code == 200


def test_deleting_own_plan_does_not_touch_the_other_user(alice, bob):
    a = plan_of(alice, "nyu-cs", "Alice temp", [{"course_code": "CSCI-UA 102", "term": 2}])
    b = plan_of(bob, "cmu-me", "Bob keeps", [{"course_code": "24-101", "term": 1}])
    assert client.delete(f"/me/plans/{a['id']}", headers=alice["h"]).status_code in (200, 204)
    assert client.get(f"/me/plans/{a['id']}", headers=alice["h"]).status_code == 404
    # Bob's plan and entries survive
    kept = client.get(f"/me/plans/{b['id']}", headers=bob["h"]).json()
    assert [e["course_code"] for e in kept["entries"]] == ["24-101"]


def test_plan_ids_are_not_enumerable_across_users(alice, bob):
    # Bob probes a range of ids; he may only ever see his own.
    own = {p["id"] for p in client.get("/me/plans", headers=bob["h"]).json()}
    for pid in range(1, 40):
        r = client.get(f"/me/plans/{pid}", headers=bob["h"])
        if r.status_code == 200:
            assert r.json()["id"] in own, f"leaked plan {pid}"
        else:
            assert r.status_code == 404


# --------------------------------------------------------------------------- #
# credentials: no token, wrong token, and cross-account password effects
# --------------------------------------------------------------------------- #

USER_SCOPED = [
    ("GET", "/me", None),
    ("PATCH", "/me/profile", {"grad_year": 2030}),
    ("PATCH", "/me/password", {"current_password": "a", "new_password": "bbbbbbbbbb"}),
    ("GET", "/me/plans", None),
    ("POST", "/me/plans", {"program_id": "nyu-cs", "name": "x"}),
    ("GET", "/me/plans/1", None),
    ("PATCH", "/me/plans/1", {"name": "x"}),
    ("DELETE", "/me/plans/1", None),
    ("PUT", "/me/plans/1/entries", []),
    ("PATCH", "/me/plans/1/entries/CSCI-UA 102", {"term": 1}),
    ("GET", "/me/plans/1/evaluate", None),
]


@pytest.mark.parametrize("method,url,body", USER_SCOPED)
def test_no_token_is_401(method, url, body):
    assert client.request(method, url, json=body).status_code == 401


@pytest.mark.parametrize("method,url,body", USER_SCOPED)
def test_garbage_token_is_401(method, url, body):
    h = {"Authorization": "Bearer not.a.real.token"}
    assert client.request(method, url, headers=h, json=body).status_code == 401


def test_forged_token_for_another_user_is_rejected(alice):
    # A token signed with the wrong key must not authenticate, even if its claims
    # name a real user id.
    import jwt
    forged = jwt.encode({"sub": str(alice["user"]["id"]), "ver": 0}, "wrong-secret",
                        algorithm="HS256")
    r = client.get("/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_password_change_revokes_only_that_users_sessions(alice, bob):
    r = client.patch("/me/password", headers=alice["h"],
                     json={"current_password": alice["password"],
                           "new_password": "alicebrandnew2026"})
    assert r.status_code == 200
    # Alice's old token is dead...
    assert client.get("/me", headers=alice["h"]).status_code == 401
    # ...but Bob is unaffected and still signed in
    assert client.get("/me", headers=bob["h"]).status_code == 200


def test_a_password_change_cannot_reach_another_account(alice):
    """There is no parameter by which one caller can target another account.

    /me/password acts only on the authenticated caller, so the honest test is that
    a *different* user changing their own password leaves this account's credentials
    working, and that the changer's new password does not open this account.
    """
    carol = make_user(first="Carol", last="Diaz", password="carolpassword2026")
    assert client.patch("/me/password", headers=carol["h"],
                        json={"current_password": "carolpassword2026",
                              "new_password": "carolbrandnew2026"}).status_code == 200

    # Alice's own password still works and is unchanged...
    assert client.post("/auth/login", json={"email": alice["email"],
                                            "password": alice["password"]}).status_code == 200
    # ...and Carol's new password does not open Alice's account.
    assert client.post("/auth/login", json={"email": alice["email"],
                                            "password": "carolbrandnew2026"}).status_code == 401


def test_wrong_current_password_is_refused(alice):
    assert client.patch("/me/password", headers=alice["h"],
                        json={"current_password": "not-my-password",
                              "new_password": "somethingnew2026"}).status_code == 403


def test_logout_everywhere_is_scoped_to_the_caller(alice, bob):
    assert client.post("/auth/logout-everywhere", headers=alice["h"]).status_code == 200
    assert client.get("/me", headers=alice["h"]).status_code == 401
    assert client.get("/me", headers=bob["h"]).status_code == 200


# --------------------------------------------------------------------------- #
# structural guard: a future /me route cannot forget to scope itself
# --------------------------------------------------------------------------- #

def test_all_me_routes_require_authentication():
    """Every registered /me* route must reject an unauthenticated request.

    This walks the live route table, so a newly added endpoint that forgets the
    current_user dependency fails here rather than in production.
    """
    checked = 0
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/me"):
            continue
        for method in (getattr(route, "methods", set()) or set()) - {"HEAD", "OPTIONS"}:
            url = path.replace("{plan_id}", "1").replace("{code}", "CSCI-UA 102")
            r = client.request(method, url, json={} if method != "GET" else None)
            assert r.status_code == 401, f"{method} {path} -> {r.status_code} (unscoped?)"
            checked += 1
    assert checked >= 11, f"expected to check the /me surface, only saw {checked}"


# --------------------------------------------------------------------------- #
# client-side guard: the bundle must not carry one account's plan into the next
# --------------------------------------------------------------------------- #

def test_bundle_clears_plan_edits_on_sign_out_and_replaces_on_sign_in():
    """Regression guard for a cross-user leak found in the browser.

    The server was never at fault, but the client used to (a) leave ``state.edits``
    and its localStorage copy in place on sign-out and (b) *merge* the next user's
    plans onto those leftovers — so account B saw account A's edits for any program
    B had no plan for. Both halves are asserted here against the shipped bundle.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "Compass Planner.html").read_text(
        encoding="utf-8")
    # sign-out wipes the departing user's edits
    assert "this.saveEditsToLS({});" in src, "sign-out must clear the stored edits"
    assert "edits: {}, editV:" in src, "sign-out must clear in-memory edits"
    # sign-in replaces rather than merges
    assert "const edits = { ...(this.state.edits || {}) };\n        plans.forEach" not in src, \
        "syncPlansFromServer must not merge onto existing edits"
    assert "// Replace, do not merge" in src


# --------------------------------------------------------------------------- #
# sign-up form: the program picker must never be a dead control
# --------------------------------------------------------------------------- #

def test_signup_form_handles_an_unloaded_program_list():
    """Regression guard: the school/major picker used to render with zero options
    when the catalog had not loaded (API down, or simply still in flight), so it
    looked broken — clicking did nothing and no message explained why. The catalog
    error screen was also stacked *below* the login gate, hiding the explanation.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "Compass Planner.html").read_text(
        encoding="utf-8")
    # the picker only renders when programs exist, with a labelled fallback otherwise
    assert "programsReady" in src and "programsPending" in src
    assert "Loading programs" in src
    assert "Program list unavailable" in src
    # sign-up refuses to submit without a program list
    assert "Cannot load the program list" in src
    # the catalog error screen must sit above the gate (z 420 > z 400)
    assert "z-index:420" in src, "catalog error must render above the login gate"
