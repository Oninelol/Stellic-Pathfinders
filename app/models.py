"""User-owned tables. No catalog table ever enters this metadata.

``program_id`` and ``course_code`` are plain strings, not foreign keys: the catalog
lives in seed JSON, and course codes must accept transfer credits from institutions
this catalog has never heard of. Unknown codes surface in ``unknown_codes`` at
evaluation time rather than being rejected at write time.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    # The school + major chosen at sign-up. A plain string id (e.g. "nyu-cs"),
    # validated against the seed catalog at write time, never a foreign key.
    program_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # scrypt hash, stored as "scrypt$n$r$p$salt_hex$hash_hex" — never a plaintext password
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # bumped on password change / "sign out everywhere" so old tokens stop verifying
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    plans: Mapped[list["Plan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class Plan(Base):
    """A student's plan for one program. A user may hold several — "what if I
    switched majors" is the most useful thing a degree planner does."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    program_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), default="My plan")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped[User] = relationship(back_populates="plans")
    entries: Mapped[list["PlanEntry"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan")


class PlanEntry(Base):
    """One course placement in a plan. ``grade``/``grading_basis`` exist now and are
    unused until the degree audit — both schools require C or better toward the
    major and NYU excludes Pass/Fail, so the audit is blocked on these columns."""

    __tablename__ = "plan_entries"
    __table_args__ = (UniqueConstraint("plan_id", "course_code", name="uq_plan_course"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    course_code: Mapped[str] = mapped_column(String(64), nullable=False)
    term: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PLANNED")
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    grading_basis: Mapped[str] = mapped_column(String(16), default="LETTER")

    plan: Mapped[Plan] = relationship(back_populates="entries")
