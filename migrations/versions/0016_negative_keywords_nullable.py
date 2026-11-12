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
    # 先把两列都改成可空（MySQL 的 UPDATE ... = NULL 要求列已可空）
    op.alter_column("skill_toggles", "negative_keywords", existing_type=sa.String(256), nullable=True, server_default=None)
    op.alter_column("custom_skills", "negative_keywords", existing_type=sa.String(256), nullable=True, server_default=None)
    # 再把历史空串回填为 NULL（NULL = 用内置默认；"" = 用户显式清空）
    op.execute("UPDATE skill_toggles SET negative_keywords = NULL WHERE negative_keywords = ''")
    op.execute("UPDATE custom_skills SET negative_keywords = NULL WHERE negative_keywords = ''")


def downgrade() -> None:
    # 回滚必须对称：两表都先回填空串，再改回 NOT NULL（否则回滚即坏数据）
    op.execute("UPDATE skill_toggles SET negative_keywords = '' WHERE negative_keywords IS NULL")
    op.execute("UPDATE custom_skills SET negative_keywords = '' WHERE negative_keywords IS NULL")
    op.alter_column("skill_toggles", "negative_keywords", existing_type=sa.String(256), nullable=False, server_default="")
    op.alter_column("custom_skills", "negative_keywords", existing_type=sa.String(256), nullable=False, server_default="")
