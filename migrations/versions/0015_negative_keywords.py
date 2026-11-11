"""add negative_keywords to skills

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skill_toggles", sa.Column("negative_keywords", sa.String(256), nullable=False, server_default=""))
    op.add_column("custom_skills", sa.Column("negative_keywords", sa.String(256), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("custom_skills", "negative_keywords")
    op.drop_column("skill_toggles", "negative_keywords")
