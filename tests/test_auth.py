"""Authentication and per-user plan storage.

Runs against a throwaway SQLite file per test session — no network, no provider.
"""

import pytest

# conftest.py points DATABASE_URL at a throwaway file before any app import.
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(engine)
client = TestClient(app)

_n = {"i": 0}


def new_user(remember=False):
    _n["i"] += 1
    email = f"u{_n['i']}@example.edu"
    r = client.post("/auth/signup", json={"email": email, "password": "hunter2hunter2",
                                          "display_name": "Test", "remember": remember})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["user"], {"Authorization": f"Bearer {body['token']}"}, body


# --------------------------------------------------------------------------- #
# passwords + tokens
# --------------------------------------------------------------------------- #

def test_password_hash_roundtrip_and_never_plaintext():
    h = auth.hash_password("s3cret-passphrase")
    assert "s3cret-passphrase" not in h and h.startswith("scrypt$")
    assert auth.verify_password("s3cret-passphrase", h)
    assert not auth.verify_password("nope", h)


def test_signup_login_and_me():
    user, headers, _ = new_user()
    me = client.get("/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == user["email"]
    # login returns a working token for the same account
    r = client.post("/auth/login", json={"email": user["email"], "password": "hunter2hunter2"})
    assert r.status_code == 200
    h2 = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/me", headers=h2).json()["id"] == user["id"]


def test_duplicate_email_rejected():
    user, _, _ = new_user()
    r = client.post("/auth/signup", json={"email": user["email"], "password": "another-password"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "email_taken"


def test_weak_password_rejected():
    r = client.post("/auth/signup", json={"email": "weak@example.edu", "password": "short"})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "weak_password"


def test_wrong_password_does_not_reveal_account_existence():
    user, _, _ = new_user()
    a = client.post("/auth/login", json={"email": user["email"], "password": "wrong-password"})
    b = client.post("/auth/login", json={"email": "ghost@example.edu", "password": "wrong-password"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"]["message"] == b.json()["detail"]["message"]


def test_no_token_and_bad_token_are_distinguishable_401s():
    anon = client.get("/me")
    assert anon.status_code == 401 and anon.json()["detail"]["error"] == "no_token"
    bad = client.get("/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert bad.status_code == 401 and bad.json()["detail"]["error"] == "token_invalid"


def test_remember_me_gives_a_longer_session():
    _, _, short = new_user(remember=False)
    _, _, long_ = new_user(remember=True)
    assert short["remember"] is False and long_["remember"] is True
    assert long_["expires_in"] > short["expires_in"]
    assert short["expires_in"] == auth.SESSION_HOURS * 3600
    assert long_["expires_in"] == auth.REMEMBER_DAYS * 86400


def test_logout_everywhere_invalidates_existing_tokens():
    _, headers, _ = new_user()
    assert client.get("/me", headers=headers).status_code == 200
    assert client.post("/auth/logout-everywhere", headers=headers).status_code == 200
    again = client.get("/me", headers=headers)
    assert again.status_code == 401 and again.json()["detail"]["error"] == "token_revoked"


# --------------------------------------------------------------------------- #
# public endpoints stay anonymous
# --------------------------------------------------------------------------- #

def test_catalog_and_evaluate_stay_public():
    """Named explicitly: every read-only + evaluate endpoint with NO Authorization."""
    assert client.get("/healthz").status_code == 200
    assert client.get("/schools").status_code == 200
    assert client.get("/programs/nyu-cs/coursemap").status_code == 200
    assert client.get("/programs/nyu-cs/courses/CSCI-UA 102").status_code == 200
    assert client.post("/programs/nyu-cs/evaluate", json={"edits": {}}).status_code == 200


# --------------------------------------------------------------------------- #
# per-user plans
# --------------------------------------------------------------------------- #

def test_plan_roundtrip_saves_per_user():
    _, headers, _ = new_user()
    r = client.post("/me/plans", json={"program_id": "nyu-cs", "name": "Main"}, headers=headers)
    assert r.status_code == 201
    pid = r.json()["id"]
    client.put(f"/me/plans/{pid}/entries", headers=headers, json=[
        {"course_code": "CSCI-UA 102", "term": 2, "status": "COMPLETE", "grade": "A-"},
        {"course_code": "CSCI-UA 310", "term": 5},
    ])
    got = client.get(f"/me/plans/{pid}", headers=headers).json()
    assert [e["course_code"] for e in got["entries"]] == ["CSCI-UA 102", "CSCI-UA 310"]
    assert got["is_primary"] is True  # first plan is primary


def test_grades_roundtrip_with_basis():
    _, headers, _ = new_user()
    pid = client.post("/me/plans", json={"program_id": "nyu-cs"}, headers=headers).json()["id"]
    client.put(f"/me/plans/{pid}/entries", headers=headers, json=[
        {"course_code": "CSCI-UA 102", "term": 2, "status": "COMPLETE",
         "grade": "B+", "grading_basis": "LETTER"},
        {"course_code": "EXPOS-UA 1", "term": 0, "status": "COMPLETE",
         "grade": "P", "grading_basis": "PASS_FAIL"},
    ])
    entries = {e["course_code"]: e for e in
               client.get(f"/me/plans/{pid}", headers=headers).json()["entries"]}
    assert entries["CSCI-UA 102"]["grade"] == "B+"
    assert entries["EXPOS-UA 1"]["grading_basis"] == "PASS_FAIL"


def test_another_users_plan_is_404_not_403():
    _, a_headers, _ = new_user()
    _, b_headers, _ = new_user()
    pid = client.post("/me/plans", json={"program_id": "nyu-cs"}, headers=a_headers).json()["id"]
    for call in (
        lambda: client.get(f"/me/plans/{pid}", headers=b_headers),
        lambda: client.patch(f"/me/plans/{pid}", json={"name": "x"}, headers=b_headers),
        lambda: client.delete(f"/me/plans/{pid}", headers=b_headers),
        lambda: client.put(f"/me/plans/{pid}/entries", json=[], headers=b_headers),
        lambda: client.get(f"/me/plans/{pid}/evaluate", headers=b_headers),
    ):
        assert call().status_code == 404


def test_plans_are_isolated_per_user():
    _, a, _ = new_user()
    _, b, _ = new_user()
    client.post("/me/plans", json={"program_id": "nyu-cs", "name": "A plan"}, headers=a)
    assert [p["name"] for p in client.get("/me/plans", headers=b).json()] == []
    assert [p["name"] for p in client.get("/me/plans", headers=a).json()] == ["A plan"]


def test_delete_cascades_entries():
    _, headers, _ = new_user()
    pid = client.post("/me/plans", json={"program_id": "nyu-cs"}, headers=headers).json()["id"]
    client.put(f"/me/plans/{pid}/entries", headers=headers,
               json=[{"course_code": "CSCI-UA 102", "term": 2}])
    assert client.delete(f"/me/plans/{pid}", headers=headers).status_code == 204
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import PlanEntry
    with SessionLocal() as db:
        orphans = db.scalars(select(PlanEntry).where(PlanEntry.plan_id == pid)).all()
    assert orphans == []


def test_setting_second_plan_primary_unsets_the_first():
    _, headers, _ = new_user()
    p1 = client.post("/me/plans", json={"program_id": "nyu-cs"}, headers=headers).json()
    p2 = client.post("/me/plans", json={"program_id": "cmu-cs"}, headers=headers).json()
    assert p1["is_primary"] and not p2["is_primary"]
    client.patch(f"/me/plans/{p2['id']}", json={"is_primary": True}, headers=headers)
    plans = {p["id"]: p["is_primary"] for p in client.get("/me/plans", headers=headers).json()}
    assert plans[p2["id"]] is True and plans[p1["id"]] is False


def test_unknown_program_id_rejected_with_known_list():
    _, headers, _ = new_user()
    r = client.post("/me/plans", json={"program_id": "nope"}, headers=headers)
    assert r.status_code == 422 and "nyu-cs" in r.json()["detail"]["known_programs"]


def test_unknown_course_saves_and_surfaces_in_unknown_codes():
    _, headers, _ = new_user()
    pid = client.post("/me/plans", json={"program_id": "nyu-cs"}, headers=headers).json()["id"]
    client.put(f"/me/plans/{pid}/entries", headers=headers,
               json=[{"course_code": "XFER 200", "term": 3}])
    ev = client.get(f"/me/plans/{pid}/evaluate", headers=headers).json()
    assert "XFER 200" in ev["unknown_codes"]


def test_plan_evaluate_matches_stateless_evaluate():
    """Acceptance: the two evaluate paths return identical responses."""
    _, headers, _ = new_user()
    pid = client.post("/me/plans", json={"program_id": "nyu-cs"}, headers=headers).json()["id"]
    entries = [{"course_code": "CSCI-UA 102", "term": 6}]
    client.put(f"/me/plans/{pid}/entries", headers=headers, json=entries)

    from app import catalog
    from app.routes_user import entries_to_edits
    from app.models import PlanEntry
    cat = catalog.get("nyu-cs")
    edits = entries_to_edits(cat, [PlanEntry(course_code="CSCI-UA 102", term=6)])

    server = client.get(f"/me/plans/{pid}/evaluate", headers=headers).json()
    stateless = client.post("/programs/nyu-cs/evaluate", json={"edits": edits}).json()
    assert server == stateless


def test_plan_endpoints_require_auth():
    for call in (
        lambda: client.get("/me/plans"),
        lambda: client.post("/me/plans", json={"program_id": "nyu-cs"}),
    ):
        assert call().status_code == 401


# --------------------------------------------------------------------------- #
# sign-up captures the student's school + major
# --------------------------------------------------------------------------- #

def test_signup_stores_program_and_creates_primary_plan():
    r = client.post("/auth/signup", json={
        "email": "pat.chen@nyu.edu", "password": "compass2026pass",
        "program_id": "nyu-ee", "remember": True})
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["program_id"] == "nyu-ee"
    assert user["initials"] == "PC"          # derived from the email local part
    token = r.json()["token"]
    plans = client.get("/me/plans", headers={"Authorization": f"Bearer {token}"}).json()
    assert [(p["program_id"], p["is_primary"]) for p in plans] == [("nyu-ee", True)]


def test_signup_rejects_unknown_program():
    r = client.post("/auth/signup", json={
        "email": "nobody@nyu.edu", "password": "compass2026pass",
        "program_id": "not-a-program"})
    assert r.status_code == 422
    assert "known_programs" in str(r.json()["detail"])


def test_signup_without_program_still_works():
    # The field is optional: an account can be created and a program chosen later.
    r = client.post("/auth/signup", json={
        "email": "later@nyu.edu", "password": "compass2026pass"})
    assert r.status_code == 201
    assert r.json()["user"]["program_id"] is None
    token = r.json()["token"]
    assert client.get("/me/plans", headers={"Authorization": f"Bearer {token}"}).json() == []


def test_login_returns_program_and_initials():
    client.post("/auth/signup", json={
        "email": "dana.wu@cmu.edu", "password": "compass2026pass", "program_id": "cmu-me"})
    r = client.post("/auth/login", json={
        "email": "dana.wu@cmu.edu", "password": "compass2026pass"})
    assert r.status_code == 200
    assert r.json()["user"]["program_id"] == "cmu-me"
    assert r.json()["user"]["initials"] == "DW"


# --------------------------------------------------------------------------- #
# the student's name, collected on the sign-up form
# --------------------------------------------------------------------------- #

def test_signup_captures_first_and_last_name():
    r = client.post("/auth/signup", json={
        "email": "ada.lovelace@nyu.edu", "password": "compass2026pass",
        "first_name": "Ada", "last_name": "Lovelace", "program_id": "nyu-cbe"})
    assert r.status_code == 201
    u = r.json()["user"]
    assert (u["first_name"], u["last_name"], u["full_name"]) == ("Ada", "Lovelace", "Ada Lovelace")
    # initials come from the real name, not the email
    assert u["initials"] == "AL"
    assert u["display_name"] == "Ada Lovelace"


def test_me_returns_the_name_for_the_identity_block():
    r = client.post("/auth/signup", json={
        "email": "grace.hopper@cmu.edu", "password": "compass2026pass",
        "first_name": "Grace", "last_name": "Hopper", "program_id": "cmu-cs"})
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    me = client.get("/me", headers=headers).json()
    assert me["full_name"] == "Grace Hopper"
    assert me["initials"] == "GH"
    assert me["program_id"] == "cmu-cs"


def test_name_is_optional_and_initials_fall_back_to_email():
    r = client.post("/auth/signup", json={
        "email": "solo@nyu.edu", "password": "compass2026pass"})
    u = r.json()["user"]
    assert u["first_name"] == "" and u["last_name"] == "" and u["full_name"] == ""
    assert u["initials"] == "SO"       # from the email local part


# --------------------------------------------------------------------------- #
# settings: profile picture, school/major, graduation year, password
# --------------------------------------------------------------------------- #

_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def test_profile_update_program_and_grad_year():
    _, headers, _ = new_user()
    r = client.patch("/me/profile", headers=headers,
                     json={"program_id": "cmu-me", "grad_year": 2031})
    assert r.status_code == 200
    assert r.json()["program_id"] == "cmu-me"
    assert r.json()["grad_year"] == 2031


def test_profile_rejects_unknown_program_and_bad_year():
    _, headers, _ = new_user()
    assert client.patch("/me/profile", headers=headers,
                        json={"program_id": "nope"}).status_code == 422
    assert client.patch("/me/profile", headers=headers,
                        json={"grad_year": 1200}).status_code == 422


def test_avatar_set_and_cleared():
    _, headers, _ = new_user()
    r = client.patch("/me/profile", headers=headers, json={"avatar": _PNG})
    assert r.status_code == 200 and r.json()["avatar"] == _PNG
    # an empty string clears it
    r = client.patch("/me/profile", headers=headers, json={"avatar": ""})
    assert r.status_code == 200 and r.json()["avatar"] is None


def test_avatar_must_be_an_image_and_bounded():
    _, headers, _ = new_user()
    assert client.patch("/me/profile", headers=headers,
                        json={"avatar": "data:text/html,<script>"}).status_code == 422
    huge = "data:image/png;base64," + ("A" * 400_000)
    assert client.patch("/me/profile", headers=headers,
                        json={"avatar": huge}).status_code == 413


def test_password_change_requires_current_and_revokes_tokens():
    _, headers, body = new_user()
    email = body["user"]["email"]
    # wrong current password is refused
    assert client.patch("/me/password", headers=headers,
                        json={"current_password": "nope",
                              "new_password": "brandnewpass2026"}).status_code == 403
    # correct current password succeeds
    assert client.patch("/me/password", headers=headers,
                        json={"current_password": "hunter2hunter2",
                              "new_password": "brandnewpass2026"}).status_code == 200
    # the old token no longer verifies, and the new password works
    assert client.get("/me", headers=headers).status_code == 401
    assert client.post("/auth/login", json={"email": email,
                                            "password": "brandnewpass2026"}).status_code == 200


def test_password_change_rejects_a_weak_new_password():
    _, headers, _ = new_user()
    r = client.patch("/me/password", headers=headers,
                     json={"current_password": "hunter2hunter2", "new_password": "short"})
    assert r.status_code == 422


def test_settings_endpoints_require_auth():
    assert client.patch("/me/profile", json={"grad_year": 2030}).status_code == 401
    assert client.patch("/me/password", json={"current_password": "a",
                                              "new_password": "b"}).status_code == 401


# --------------------------------------------------------------------------- #
# pigeon onboarding answers
# --------------------------------------------------------------------------- #

def test_pigeon_starts_unanswered_and_round_trips():
    _, h, _ = new_user()
    assert client.get("/me", headers=h).json()["pigeon"] is None

    answers = {"fields": ["Technology & Engineering"], "specifics": ["machine learning"],
               "goals": ["Apply to 3 internships", "Raise my GPA", "Build my resume"],
               "intl": True}
    r = client.patch("/me/profile", json={"pigeon": answers}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["pigeon"] == answers
    assert client.get("/me", headers=h).json()["pigeon"] == answers


def test_pigeon_empty_object_resets_to_unanswered():
    _, h, _ = new_user()
    client.patch("/me/profile", json={"pigeon": {"goals": ["a"]}}, headers=h)
    r = client.patch("/me/profile", json={"pigeon": {}}, headers=h)
    assert r.json()["pigeon"] is None


def test_pigeon_answers_are_per_user():
    _, ha, _ = new_user()
    _, hb, _ = new_user()
    client.patch("/me/profile", json={"pigeon": {"goals": ["alice only"]}}, headers=ha)
    # B never answered, and must not see A's answers.
    assert client.get("/me", headers=hb).json()["pigeon"] is None
    assert client.get("/me", headers=ha).json()["pigeon"] == {"goals": ["alice only"]}


def test_pigeon_rejects_oversized_answers():
    _, h, _ = new_user()
    r = client.patch("/me/profile", json={"pigeon": {"goals": ["x" * 25000]}}, headers=h)
    assert r.status_code == 413


def test_pigeon_survives_corrupt_stored_json():
    """A bad row reads as unanswered instead of 500-ing every /me for that user."""
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import User
    u, h, _ = new_user()
    db = SessionLocal()
    row = db.scalar(select(User).where(User.email == u["email"]))
    row.pigeon = "{not json"
    db.commit()
    assert client.get("/me", headers=h).json()["pigeon"] is None
