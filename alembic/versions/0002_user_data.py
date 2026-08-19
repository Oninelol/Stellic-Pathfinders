"""user data: plans and plan entries

Revision ID: 0002_user_data
Revises: 0001_users
Create Date: 2026-08-19

program_id and course_code are strings, not foreign keys: the catalog is not in this
database, and transfer credits must be storable.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_user_data"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_plans_user_id", "plans", ["user_id"])
    op.create_table(
        "plan_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(),
                  sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_code", sa.String(length=64), nullable=False),
        sa.Column("term", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("grade", sa.String(length=8), nullable=True),
        sa.Column("grading_basis", sa.String(length=16), nullable=True),
        sa.UniqueConstraint("plan_id", "course_code", name="uq_plan_course"),
    )
    op.create_index("ix_plan_entries_plan_id", "plan_entries", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_entries_plan_id", table_name="plan_entries")
    op.drop_table("plan_entries")
    op.drop_index("ix_plans_user_id", table_name="plans")
    op.drop_table("plans")
