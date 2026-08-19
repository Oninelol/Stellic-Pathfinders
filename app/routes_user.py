"""Authentication and per-user plan storage.

Every endpoint here is scoped to ``current_user``. Another user's resource id
returns **404, not 403** — the API does not confirm the existence of things the
caller cannot see.

The catalog endpoints and ``POST /programs/{id}/evaluate`` stay public and
anonymous: the catalog is not user data and evaluation is stateless.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth, catalog, schemas
from app.db import get_db
from app.models import Plan, PlanEntry, User

router = APIRouter()


# --------------------------------------------------------------------------- #
# request/response models
# --------------------------------------------------------------------------- #

class SignupIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str = ""
    remember: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember: bool = False


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str


class TokenOut(BaseModel):
    token: str
    expires_in: int
    remember: bool
    user: UserOut


class EntryIn(BaseModel):
    course_code: str
    term: int
    status: str = "PLANNED"
    grade: Optional[str] = None
    grading_basis: str = "LETTER"


class EntryOut(EntryIn):
    pass


class PlanIn(BaseModel):
    program_id: str
    name: str = "My plan"
    entries: list[EntryIn] = Field(default_factory=list)


class PlanPatch(BaseModel):
    name: Optional[str] = None
    is_primary: Optional[bool] = None


class PlanOut(BaseModel):
    id: int
    program_id: str
    name: str
    is_primary: bool
    entries: list[EntryOut]


def _user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "display_name": u.display_name or ""}


def _plan_out(p: Plan) -> dict:
    return {
        "id": p.id, "program_id": p.program_id, "name": p.name,
        "is_primary": bool(p.is_primary),
        "entries": [
            {"course_code": e.course_code, "term": e.term, "status": e.status,
             "grade": e.grade, "grading_basis": e.grading_basis}
            for e in sorted(p.entries, key=lambda e: (e.term, e.course_code))
        ],
    }


def _check_program(program_id: str) -> None:
    known = sorted(catalog.load_all())
    if program_id not in known:
        raise HTTPException(status_code=422, detail={
            "error": f"unknown program id {program_id!r}", "known_programs": known})


def _own_plan(plan_id: int, user: User, db: Session) -> Plan:
    """A plan the caller owns, or 404. Never 403 — do not leak existence."""
    p = db.get(Plan, plan_id)
    if p is None or p.user_id != user.id:
        raise HTTPException(status_code=404, detail={"error": f"no plan {plan_id}"})
    return p


# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #

@router.post("/auth/signup", response_model=TokenOut, status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail={
            "error": "email_taken", "message": "That email already has an account."})
    problem = auth.password_problem(body.password)
    if problem:
        raise HTTPException(status_code=422, detail={"error": "weak_password", "message": problem})
    user = User(email=email, display_name=(body.display_name or "").strip(),
                password_hash=auth.hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token, ttl = auth.create_token(user, body.remember)
    return {"token": token, "expires_in": ttl, "remember": body.remember,
            "user": _user_out(user)}


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    # One message for both "no such email" and "wrong password" — do not disclose
    # which addresses have accounts.
    if user is None or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail={
            "error": "bad_credentials", "message": "Email or password is incorrect."})
    token, ttl = auth.create_token(user, body.remember)
    return {"token": token, "expires_in": ttl, "remember": body.remember,
            "user": _user_out(user)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(auth.current_user)) -> dict:
    return _user_out(user)


@router.post("/auth/logout-everywhere", response_model=UserOut)
def logout_everywhere(user: User = Depends(auth.current_user),
                      db: Session = Depends(get_db)) -> dict:
    """Invalidate every issued token for this user by bumping its version."""
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return _user_out(user)


# --------------------------------------------------------------------------- #
# plans
# --------------------------------------------------------------------------- #

@router.get("/me/plans", response_model=list[PlanOut])
def list_plans(user: User = Depends(auth.current_user),
               db: Session = Depends(get_db)) -> list[dict]:
    plans = db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.id)).all()
    return [_plan_out(p) for p in plans]


@router.post("/me/plans", response_model=PlanOut, status_code=201)
def create_plan(body: PlanIn, user: User = Depends(auth.current_user),
                db: Session = Depends(get_db)) -> dict:
    _check_program(body.program_id)
    first = not db.scalar(select(Plan).where(Plan.user_id == user.id))
    p = Plan(user_id=user.id, program_id=body.program_id, name=body.name, is_primary=first)
    for e in body.entries:
        p.entries.append(PlanEntry(**e.model_dump()))
    db.add(p)
    db.commit()
    db.refresh(p)
    return _plan_out(p)


@router.get("/me/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, user: User = Depends(auth.current_user),
             db: Session = Depends(get_db)) -> dict:
    return _plan_out(_own_plan(plan_id, user, db))


@router.patch("/me/plans/{plan_id}", response_model=PlanOut)
def patch_plan(plan_id: int, body: PlanPatch, user: User = Depends(auth.current_user),
               db: Session = Depends(get_db)) -> dict:
    p = _own_plan(plan_id, user, db)
    if body.name is not None:
        p.name = body.name
    if body.is_primary:
        # at most one primary per user, cleared in the same transaction
        for other in db.scalars(select(Plan).where(Plan.user_id == user.id)).all():
            other.is_primary = (other.id == p.id)
    db.commit()
    db.refresh(p)
    return _plan_out(p)


@router.delete("/me/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(auth.current_user),
                db: Session = Depends(get_db)) -> Response:
    """Deleting a plan cascades to its entries; no orphans."""
    db.delete(_own_plan(plan_id, user, db))
    db.commit()
    return Response(status_code=204)


@router.put("/me/plans/{plan_id}/entries", response_model=PlanOut)
def replace_entries(plan_id: int, entries: list[EntryIn] = Body(...),
                    user: User = Depends(auth.current_user),
                    db: Session = Depends(get_db)) -> dict:
    """Replace the whole entry set. The board holds the plan in memory, so a full
    replace avoids a merge protocol."""
    p = _own_plan(plan_id, user, db)
    p.entries.clear()
    db.flush()
    seen: set[str] = set()
    for e in entries:
        if e.course_code in seen:      # the (plan, course) uniqueness, enforced early
            continue
        seen.add(e.course_code)
        p.entries.append(PlanEntry(**e.model_dump()))
    db.commit()
    db.refresh(p)
    return _plan_out(p)


@router.patch("/me/plans/{plan_id}/entries/{code}", response_model=PlanOut)
def patch_entry(plan_id: int, code: str, body: dict = Body(...),
                user: User = Depends(auth.current_user),
                db: Session = Depends(get_db)) -> dict:
    """Move or grade one course — the common drag-one-course case."""
    p = _own_plan(plan_id, user, db)
    entry = next((e for e in p.entries if e.course_code == code), None)
    if entry is None:
        entry = PlanEntry(course_code=code, term=int(body.get("term", -1)))
        p.entries.append(entry)
    for field in ("term", "status", "grade", "grading_basis"):
        if field in body:
            setattr(entry, field, body[field])
    db.commit()
    db.refresh(p)
    return _plan_out(p)


@router.get("/me/plans/{plan_id}/evaluate", response_model=schemas.EvaluateResponse)
def evaluate_plan(plan_id: int, user: User = Depends(auth.current_user),
                  db: Session = Depends(get_db)) -> dict:
    """Same response shape — and the same function — as POST /programs/{id}/evaluate."""
    p = _own_plan(plan_id, user, db)
    _check_program(p.program_id)
    cat = catalog.get(p.program_id)
    edits = entries_to_edits(cat, p.entries)
    return schemas.evaluate_edits(cat, edits)


def entries_to_edits(cat: catalog.Catalog, entries) -> dict:
    """Express stored entries as the edit model the evaluator already speaks.

    A stored entry whose term differs from the published curriculum is a ``moved``;
    one the catalog has never heard of is an ``added`` row (it will surface in
    ``unknown_codes``); a published course with no entry is ``removed``.
    """
    published = {r["c"]: r for r in cat.graph_courses() if not r.get("ghost")}
    moved: dict[str, int] = {}
    added: list[dict] = []
    for e in entries:
        base = published.get(e.course_code)
        if base is None:
            added.append({"c": e.course_code, "n": e.course_code, "cr": 0,
                          "t": e.term, "s": "plan", "g": "free"})
        elif base.get("t") != e.term:
            moved[e.course_code] = e.term
    kept = {e.course_code for e in entries}
    removed = [c for c in published if c not in kept] if entries else []
    return {"moved": moved, "added": added, "removed": removed}
