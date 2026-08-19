"""user names: first and last, collected on sign-up

Revision ID: 0004_user_names
Revises: 0003_user_program
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_user_names"
down_revision = "0003_user_program"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
