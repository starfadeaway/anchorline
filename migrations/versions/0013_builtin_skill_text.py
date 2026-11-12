"""add skill_toggles description/instructions overrides

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skill_toggles", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("skill_toggles", sa.Column("instructions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("skill_toggles", "instructions")
    op.drop_column("skill_toggles", "description")
