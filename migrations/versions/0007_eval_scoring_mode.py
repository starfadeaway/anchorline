"""add eval_runs.scoring_mode

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eval_runs",
        sa.Column("scoring_mode", sa.String(length=16), nullable=False, server_default="deterministic"),
    )
    # 168 的 gotchas 题是 LLM judge；其余是确定性判分
    op.execute("UPDATE eval_runs SET scoring_mode='judge' WHERE benchmark='v2-web-168'")


def downgrade() -> None:
    op.drop_column("eval_runs", "scoring_mode")
