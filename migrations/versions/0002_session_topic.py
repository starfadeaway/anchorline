"""add session.topic

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("topic", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "topic")
