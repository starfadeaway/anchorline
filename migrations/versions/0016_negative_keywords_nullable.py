"""negative_keywords three-state (nullable)

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("skill_toggles", "negative_keywords", existing_type=sa.String(256), nullable=True, server_default=None)
    op.execute("UPDATE skill_toggles SET negative_keywords = NULL WHERE negative_keywords = ''")
    op.alter_column("custom_skills", "negative_keywords", existing_type=sa.String(256), nullable=True, server_default=None)


def downgrade() -> None:
    op.execute("UPDATE skill_toggles SET negative_keywords = '' WHERE negative_keywords IS NULL")
    op.alter_column("skill_toggles", "negative_keywords", existing_type=sa.String(256), nullable=False, server_default="")
    op.alter_column("custom_skills", "negative_keywords", existing_type=sa.String(256), nullable=False, server_default="")
