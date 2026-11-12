"""add custom_skills.memory_entity

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("custom_skills", sa.Column("memory_entity", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("custom_skills", "memory_entity")
