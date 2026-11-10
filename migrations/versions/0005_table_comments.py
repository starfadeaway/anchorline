"""add table comments

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-10
"""
from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

COMMENTS = {
    "facts": "事实记忆：实体/属性/值/生效时间；历史不物理删除（valid_to 标记失效）",
    "sessions": "会话（聊天/评测）：标题、主题标签、创建时间",
    "messages": "会话消息（user / assistant）",
    "traces": "检索/聊天轨迹：预算、注入事实、召回明细、终止原因",
    "eval_runs": "评测结果：臂 × 题 × 预算的逐题得分",
    "review_decisions": "人工裁决金标：保留/失效/原因/操作者",
    "alembic_version": "Alembic 迁移版本（工具表，只存一行）",
}


def upgrade() -> None:
    for table, comment in COMMENTS.items():
        op.execute(f"ALTER TABLE `{table}` COMMENT = '{comment}'")


def downgrade() -> None:
    for table in COMMENTS:
        op.execute(f"ALTER TABLE `{table}` COMMENT = ''")
