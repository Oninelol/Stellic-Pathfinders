"""user settings: avatar image and graduation year

Revision ID: 0005_user_settings
Revises: 0004_user_names
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_user_settings"
down_revision = "0004_user_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A small data: URL. There is no object store in this project, and a profile
    # picture is a few tens of KB — the API caps the size on write.
    op.add_column("users", sa.Column("avatar", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("grad_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "grad_year")
    op.drop_column("users", "avatar")
