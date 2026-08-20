"""user.pigeon — onboarding quiz answers as a JSON string

Revision ID: 0006_user_pigeon
Revises: 0005_user_settings
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_user_pigeon"
down_revision = "0005_user_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable with no server default: NULL is meaningful here — it is how the
    # app knows this student has never answered the pigeon's questions.
    op.add_column("users", sa.Column("pigeon", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "pigeon")
