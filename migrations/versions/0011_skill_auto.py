"""add skill auto-activation + facts.skill_name

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("custom_skills", sa.Column("auto_activate", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("custom_skills", sa.Column("trigger_keywords", sa.String(256), nullable=False, server_default=""))
    op.add_column("facts", sa.Column("skill_name", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("facts", "skill_name")
    op.drop_column("custom_skills", "trigger_keywords")
    op.drop_column("custom_skills", "auto_activate")
