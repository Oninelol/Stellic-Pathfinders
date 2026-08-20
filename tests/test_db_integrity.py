"""Database-level guarantees for accounts and per-user data.

These assert what the *database* enforces, not what the API happens to do — a
route could be rewritten badly, but a UNIQUE constraint or a foreign key still
holds. SQLite needs foreign keys switched on per connection, so that is asserted
too: without it, ON DELETE CASCADE is silently ignored.
"""

import sqlite3

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import auth
from app.db import SessionLocal, engine
from app.models import Plan, PlanEntry, User


def _new_user(db, email):
    """Insert via the ORM so Python-side defaults (created_at, …) are applied;
    the DB-level constraints under test still fire."""
    u = User(email=email, display_name="", password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# --------------------------------------------------------------------------- #
# credentials
# --------------------------------------------------------------------------- #

def test_password_is_stored_as_a_salted_hash_never_plaintext():
    secret = "correct-horse-battery-staple"
    h = auth.hash_password(secret)
    assert secret not in h
    assert h.startswith("scrypt$")
    assert auth.verify_password(secret, h)
    assert not auth.verify_password("something-else", h)


def test_two_users_with_the_same_password_get_different_hashes():
    """Per-user salt: identical passwords must not produce identical hashes."""
    a = auth.hash_password("same-password-123")
    b = auth.hash_password("same-password-123")
    assert a != b
    assert auth.verify_password("same-password-123", a)
    assert auth.verify_password("same-password-123", b)


def test_email_is_unique_at_the_database_level():
    with SessionLocal() as db:
        _new_user(db, "dupe@example.edu")
        with pytest.raises(IntegrityError):
            _new_user(db, "dupe@example.edu")   # same address, second account
        db.rollback()


# --------------------------------------------------------------------------- #
# per-user data is linked to the account
# --------------------------------------------------------------------------- #

def test_sqlite_foreign_keys_are_enforced():
    """Without this pragma SQLite ignores every ON DELETE CASCADE in the schema."""
    with engine.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_a_plan_cannot_exist_without_a_user():
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.execute(text("insert into plans (user_id, program_id, name) "
                           "values (999999, 'nyu-cs', 'orphan')"))


def test_an_entry_cannot_exist_without_a_plan():
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.execute(text("insert into plan_entries (plan_id, course_code, term) "
                           "values (999999, 'CSCI-UA 102', 1)"))


def test_deleting_a_user_cascades_to_their_plans_and_entries():
    with SessionLocal() as db:
        u = _new_user(db, "cascade@example.edu")
        p = Plan(user_id=u.id, program_id="nyu-cs", name="p")
        db.add(p); db.commit(); db.refresh(p)
        db.add(PlanEntry(plan_id=p.id, course_code="CSCI-UA 102", term=1)); db.commit()
        uid, pid = u.id, p.id

    # delete the account row directly: the cascade must be the database's doing,
    # not the ORM's, which is what ON DELETE CASCADE + the FK pragma buys us.
    with engine.begin() as c:
        c.execute(text("delete from users where id = :u"), {"u": uid})
    with engine.connect() as c:
        assert c.execute(text("select count(*) from plans where user_id = :u"),
                         {"u": uid}).scalar() == 0
        assert c.execute(text("select count(*) from plan_entries where plan_id = :p"),
                         {"p": pid}).scalar() == 0


def test_a_course_appears_at_most_once_per_plan():
    with SessionLocal() as db:
        u = _new_user(db, "uniq@example.edu")
        p = Plan(user_id=u.id, program_id="nyu-cs", name="p")
        db.add(p); db.commit(); db.refresh(p)
        db.add(PlanEntry(plan_id=p.id, course_code="CSCI-UA 102", term=1)); db.commit()
        with pytest.raises(IntegrityError):
            db.add(PlanEntry(plan_id=p.id, course_code="CSCI-UA 102", term=3))
            db.commit()
        db.rollback()


def test_every_row_of_user_data_traces_back_to_an_account():
    """No orphans anywhere: every plan has a user and every entry has a plan."""
    with engine.connect() as c:
        assert c.execute(text(
            "select count(*) from plans p left join users u on u.id = p.user_id "
            "where u.id is null")).scalar() == 0
        assert c.execute(text(
            "select count(*) from plan_entries e left join plans p on p.id = e.plan_id "
            "where p.id is null")).scalar() == 0


# --------------------------------------------------------------------------- #
# the catalog never enters this database
# --------------------------------------------------------------------------- #

def test_no_catalog_tables_exist():
    """Course data lives in seed JSON. A catalog table here would mean two sources
    of truth and a migration every time a school revises its requirements."""
    with engine.connect() as c:
        names = {r[0] for r in c.execute(text(
            "select name from sqlite_master where type='table'"))}
    for forbidden in ("courses", "programs", "catalog", "requirements", "terms"):
        assert forbidden not in names, f"catalog table {forbidden!r} must not exist"
    assert {"users", "plans", "plan_entries"} <= names
