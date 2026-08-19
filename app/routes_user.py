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
    program_id: str | None = None   # school + major, chosen on the sign-up form
    first_name: str = ""
    last_name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember: bool = False


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    program_id: str | None = None
    initials: str = ""
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    avatar: str | None = None
    grad_year: int | None = None


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
    first = (u.first_name or "").strip()
    last = (u.last_name or "").strip()
    return {"id": u.id, "email": u.email, "display_name": u.display_name or "",
            "program_id": u.program_id, "initials": _initials(u),
            "first_name": first, "last_name": last,
            "full_name": " ".join(p for p in (first, last) if p),
            "avatar": u.avatar, "grad_year": u.grad_year}


def _initials(u: User) -> str:
    """Two letters for the avatar: the student's real initials when we have a name,
    otherwise derived from the display name or email local part."""
    first = (u.first_name or "").strip()
    last = (u.last_name or "").strip()
    if first and last:
        return (first[0] + last[0]).upper()
    src = first or (u.display_name or "").strip() or (u.email or "").split("@")[0]
    parts = [p for p in src.replace(".", " ").replace("_", " ").replace("-", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return (parts[0][:2] if parts else "?").upper()


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
    program_id = (body.program_id or "").strip() or None
    if program_id:
        _check_program(program_id)            # 422 listing known ids if unknown
    first = (body.first_name or "").strip()
    last = (body.last_name or "").strip()
    user = User(email=email,
                display_name=(body.display_name or "").strip() or " ".join(p for p in (first, last) if p),
                first_name=first or None, last_name=last or None,
                program_id=program_id,
                password_hash=auth.hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    # Give the new account a primary plan for the program they chose, so their data
    # has somewhere to live from the first edit.
    if program_id:
        db.add(Plan(user_id=user.id, program_id=program_id,
                    name="My plan", is_primary=True))
        db.commit()
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


class ProfileIn(BaseModel):
    """Every field optional — the settings panel sends only what changed."""
    first_name: str | None = None
    last_name: str | None = None
    program_id: str | None = None
    grad_year: int | None = None
    avatar: str | None = None       # data: URL, or "" to clear the picture


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


# A profile picture is stored inline as a data: URL. Cap it so the row (and every
# /me response) stays small; the client downscales before upload.
AVATAR_MAX_BYTES = 300_000
GRAD_YEAR_RANGE = (1950, 2100)


@router.patch("/me/profile", response_model=UserOut)
def update_profile(body: ProfileIn, user: User = Depends(auth.current_user),
                   db: Session = Depends(get_db)) -> dict:
    """Update the signed-in student's own details. Nothing here touches the catalog."""
    if body.program_id is not None:
        _check_program(body.program_id)      # 422 listing known ids if unknown
        user.program_id = body.program_id
    if body.grad_year is not None:
        lo, hi = GRAD_YEAR_RANGE
        if not (lo <= body.grad_year <= hi):
            raise HTTPException(status_code=422, detail={
                "error": "bad_grad_year",
                "message": f"Graduation year must be between {lo} and {hi}."})
        user.grad_year = body.grad_year
    if body.avatar is not None:
        av = body.avatar.strip()
        if av == "":
            user.avatar = None               # explicit clear
        else:
            if not av.startswith("data:image/"):
                raise HTTPException(status_code=422, detail={
                    "error": "bad_avatar", "message": "Profile picture must be an image."})
            if len(av) > AVATAR_MAX_BYTES:
                raise HTTPException(status_code=413, detail={
                    "error": "avatar_too_large",
                    "message": "That image is too large — please pick one under ~200 KB."})
            user.avatar = av
    if body.first_name is not None:
        user.first_name = body.first_name.strip() or None
    if body.last_name is not None:
        user.last_name = body.last_name.strip() or None
    if body.first_name is not None or body.last_name is not None:
        user.display_name = " ".join(
            p for p in ((user.first_name or ""), (user.last_name or "")) if p)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.patch("/me/password", response_model=UserOut)
def change_password(body: PasswordIn, user: User = Depends(auth.current_user),
                    db: Session = Depends(get_db)) -> dict:
    """Change the password. Requires the current one, and revokes existing tokens."""
    if not auth.verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail={
            "error": "wrong_password", "message": "That is not your current password."})
    problem = auth.password_problem(body.new_password)
    if problem:
        raise HTTPException(status_code=422, detail={"error": "weak_password", "message": problem})
    user.password_hash = auth.hash_password(body.new_password)
    # Bumping the version invalidates tokens minted before the change.
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)
    return _user_out(user)


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
