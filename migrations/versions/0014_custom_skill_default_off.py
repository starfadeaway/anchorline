"""custom_skills.enabled default 0

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("custom_skills", "enabled", server_default=sa.text("0"))


def downgrade() -> None:
    op.alter_column("custom_skills", "enabled", server_default=sa.text("1"))
