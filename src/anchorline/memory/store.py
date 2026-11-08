# -*- coding: utf-8 -*-
"""L2 事实存储：写入 / 失效标记（supersedes）/ 当前值 / 历史 / 文本检索。

纪律（v0.8）：
  - **不物理删除**；旧值用 `valid_to` + 新值的 `supersedes_id` 表达；
  - 唯一约束 `(entity_id, attribute, valid_from)`：同一生效时间重复写入是幂等的；
  - M1 只做确定性文本检索（LIKE）；BM25 / 向量召回在 M2 接入。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from anchorline.models import Fact


class FactStore:
    def __init__(self, db: Session):
        self.db = db

    # --- 写 ---
    def write(
        self,
        *,
        entity_id: str,
        attribute: str,
        value: str,
        valid_from: datetime,
        source_session_id: str | None = None,
        source_message_id: int | None = None,
        confidence: float = 1.0,
        fact_type: str = "semantic",
        conflict_type: str | None = None,
    ) -> Fact:
        existing = self.db.scalar(
            select(Fact).where(
                Fact.entity_id == entity_id,
                Fact.attribute == attribute,
                Fact.valid_from == valid_from,
            )
        )
        if existing is not None:
            existing.value = value
            existing.confidence = confidence
            self.db.flush()
            return existing

        old = self.current(entity_id, attribute)
        fact = Fact(
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            valid_from=valid_from,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
            confidence=confidence,
            fact_type=fact_type,
            conflict_type=conflict_type,
            supersedes_id=old.id if old is not None else None,
        )
        self.db.add(fact)
        if old is not None:
            # 旧事实失效（不删除），有效区间截止到新值生效时刻
            old.valid_to = valid_from
        self.db.flush()
        return fact

    # --- 读 ---
    def current(self, entity_id: str, attribute: str) -> Fact | None:
        return self.db.scalar(
            select(Fact)
            .where(
                Fact.entity_id == entity_id,
                Fact.attribute == attribute,
                Fact.valid_to.is_(None),
            )
            .order_by(Fact.valid_from.desc())
            .limit(1)
        )

    def history(self, entity_id: str, attribute: str) -> list[Fact]:
        return list(
            self.db.scalars(
                select(Fact)
                .where(Fact.entity_id == entity_id, Fact.attribute == attribute)
                .order_by(Fact.valid_from.asc())
            )
        )

    def search_text(self, query: str, limit: int = 20) -> list[Fact]:
        like = f"%{query}%"
        return list(
            self.db.scalars(
                select(Fact)
                .where(Fact.attribute.like(like) | Fact.value.like(like) | Fact.entity_id.like(like))
                .order_by(Fact.valid_from.desc())
                .limit(limit)
            )
        )
