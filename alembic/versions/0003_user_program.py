"""user program: the school + major chosen at sign-up

Revision ID: 0003_user_program
Revises: 0002_user_data
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_user_program"
down_revision = "0002_user_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The program the student picked when creating the account. A plain string, not a
    # foreign key — the catalog lives in seed JSON, never in this database.
    op.add_column("users", sa.Column("program_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "program_id")
