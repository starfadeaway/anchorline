"""add skill_toggles binding columns

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skill_toggles", sa.Column("memory_entity", sa.String(128), nullable=True))
    op.add_column("skill_toggles", sa.Column("auto_activate", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("skill_toggles", sa.Column("trigger_keywords", sa.String(256), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("skill_toggles", "trigger_keywords")
    op.drop_column("skill_toggles", "auto_activate")
    op.drop_column("skill_toggles", "memory_entity")
