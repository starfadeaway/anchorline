"""initial schema: sessions / messages / facts / traces / eval_runs

Revision ID: 0001
Revises:
Create Date: 2026-11-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("external_id", sa.String(128), unique=True, nullable=True),
        sa.Column("domain", sa.String(32), nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(32), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "facts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("attribute", sa.String(128), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("valid_from", sa.DateTime, nullable=False),
        sa.Column("valid_to", sa.DateTime, nullable=True),
        sa.Column("source_session_id", sa.String(128), nullable=True),
        sa.Column("source_message_id", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("supersedes_id", sa.String(32), sa.ForeignKey("facts.id"), nullable=True),
        sa.Column("fact_type", sa.String(32), nullable=False, server_default="semantic"),
        sa.Column("conflict_type", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("entity_id", "attribute", "valid_from", name="uq_fact_entity_attr_from"),
    )
    op.create_index("ix_facts_entity_id", "facts", ["entity_id"])
    op.create_index("ix_facts_attribute", "facts", ["attribute"])
    op.create_index("ix_fact_lookup", "facts", ["entity_id", "attribute"])

    op.create_table(
        "traces",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(32), nullable=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("budget_tokens", sa.Integer, nullable=False),
        sa.Column("used_tokens", sa.Integer, nullable=False),
        sa.Column("layers", sa.String(64), nullable=False),
        sa.Column("injected_fact_ids", sa.Text, nullable=True),
        sa.Column("resolution", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_traces_session_id", "traces", ["session_id"])

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("benchmark", sa.String(32), nullable=False),
        sa.Column("arm", sa.String(16), nullable=False),
        sa.Column("budget_tokens", sa.Integer, nullable=False),
        sa.Column("question_id", sa.String(64), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("reader_model", sa.String(128), nullable=False),
        sa.Column("judge_model", sa.String(128), nullable=True),
        sa.Column("judge_prompt_sha256", sa.String(64), nullable=True),
        sa.Column("config_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_eval_runs_question_id", "eval_runs", ["question_id"])


def downgrade() -> None:
    op.drop_table("eval_runs")
    op.drop_table("traces")
    op.drop_table("facts")
    op.drop_table("messages")
    op.drop_table("sessions")
