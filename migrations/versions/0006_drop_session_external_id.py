"""drop sessions.external_id (unused)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("sessions", "external_id")


def downgrade() -> None:
    op.add_column("sessions", sa.Column("external_id", sa.String(length=128), nullable=True))
    op.create_unique_constraint("uq_sessions_external_id", "sessions", ["external_id"])
