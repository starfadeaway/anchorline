"""add review_decisions

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("attribute", sa.String(length=128), nullable=True),
        sa.Column("kept_fact_id", sa.String(length=32), nullable=False),
        sa.Column("invalidated_fact_ids", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("operator", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_review_decisions_entity_id", "review_decisions", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_review_decisions_entity_id", table_name="review_decisions")
    op.drop_table("review_decisions")
