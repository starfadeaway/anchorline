# -*- coding: utf-8 -*-
"""SQLAlchemy 2 模型：事实 / 会话 / trace / eval_runs。

锁定决策（v0.8）：
  - 唯一约束 `(entity_id, attribute, valid_from)`；
  - **不物理删除**：用 `supersedes` + `valid_to` 表达失效，可回溯；
  - 向量不进 MySQL（向量在 LanceDB，MySQL 只存元数据与文本事实）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(String(32), default="chat")  # chat / web / enterprise
    # 会话主题标签（模型生成，前端按它分组；空则回退首条消息关键词）
    topic: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant / tool
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Fact(Base):
    """L2 事实条目：属性 / 值 / 生效时间 / 来源 / 置信度 / supersedes。"""

    __tablename__ = "facts"
    __table_args__ = (
        UniqueConstraint("entity_id", "attribute", "valid_from", name="uq_fact_entity_attr_from"),
        Index("ix_fact_lookup", "entity_id", "attribute"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)
    attribute: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_session_id: Mapped[str | None] = mapped_column(String(128))
    source_message_id: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("facts.id"), nullable=True)
    fact_type: Mapped[str] = mapped_column(String(32), default="semantic")  # semantic / episodic
    conflict_type: Mapped[str | None] = mapped_column(String(32))  # 时效 / 语义 / 偏好反转
    # 写入该事实时激活的技能名（可空：手工/seed/MCP 写入）
    skill_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Trace(Base):
    """召回 / 组装 / 裁决 trace：为什么注入、压缩层级、token、裁决依据。"""

    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(32), index=True)
    query: Mapped[str] = mapped_column(Text)
    budget_tokens: Mapped[int] = mapped_column(Integer)
    used_tokens: Mapped[int] = mapped_column(Integer)
    layers: Mapped[str] = mapped_column(String(64))  # 例如 "L0>L1>L2>L3"
    injected_fact_ids: Mapped[str | None] = mapped_column(Text)  # JSON 数组
    recalls: Mapped[str | None] = mapped_column(Text)  # JSON：召回明细（bm25/vector/rrf/rerank 分数）
    resolution: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReviewDecision(Base):
    """审核裁决金标：同一实体/属性冲突时保留哪条、失效哪些、原因。"""

    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)
    attribute: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kept_fact_id: Mapped[str] = mapped_column(String(32))
    invalidated_fact_ids: Mapped[str] = mapped_column(Text)  # JSON 数组
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(32), default="human")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    benchmark: Mapped[str] = mapped_column(String(32))  # v2-web / v1-ku
    arm: Mapped[str] = mapped_column(String(16))  # A / B / C1 / C2 / D / E
    budget_tokens: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float)
    # deterministic = 官方确定性判分（不调 LLM，judge 列留空）；judge = LLM 判分
    scoring_mode: Mapped[str] = mapped_column(String(16), default="deterministic")
    reader_model: Mapped[str] = mapped_column(String(128))
    judge_model: Mapped[str | None] = mapped_column(String(128))
    judge_prompt_sha256: Mapped[str | None] = mapped_column(String(64))
    config_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class SkillToggle(Base):
    """内置技能开关（可开关的提示模块；聊天时把启用技能拼进 system prompt）。"""

    __tablename__ = "skill_toggles"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class CustomSkill(Base):
    """用户自定义技能（新技能页创建；与内置技能统一注入 system prompt）。"""

    __tablename__ = "custom_skills"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    instructions: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 可选：绑定的记忆实体（如 user / user.猫）；注入该技能时附上该实体的当前事实
    memory_entity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 主题命中时自动启用（不依赖手动开关）
    auto_activate: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger_keywords: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
