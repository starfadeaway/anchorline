# -*- coding: utf-8 -*-
"""L2 事实存储：写入 / 失效标记（supersedes）/ 当前值 / 历史 / 文本检索。

纪律（v0.8）：
  - **不物理删除**；旧值用 `valid_to` + 新值的 `supersedes_id` 表达；
  - 唯一约束 `(entity_id, attribute, valid_from)`：同一生效时间重复写入是幂等的；
  - M1 只做确定性文本检索（LIKE）；BM25 / 向量召回在 M2 接入。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from anchorline.models import Fact


def _attr_tokens(text: str) -> set[str]:
    """属性名归一化分词：用于判断「同一实体的近似属性」（如 5k_pb / 5K_personal_best / 5K 最好成绩）。"""
    return {t for t in re.split(r"[\s_\-（）()/:,;、，。]+", (text or "").lower()) if t}


class FactStore:
    def __init__(self, db: Session, max_current_per_entity: int | None = None):
        self.db = db
        # 容量上限：每个实体最多保留的当前值条数（None/<=0 表示不限）
        if max_current_per_entity is None:
            try:
                from anchorline.config import Settings

                max_current_per_entity = Settings().memory_max_current_per_entity
            except Exception:
                max_current_per_entity = 200
        self.max_current_per_entity = max_current_per_entity
        # 最近一次写入触发的自动归档条数（供调用方提示用户）
        self.last_archived = 0

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
        # 规范实体：把属性误写成实体（user.乒乓球经历 且后缀=属性）时归回 user
        if isinstance(entity_id, str) and entity_id.startswith("user.") and entity_id[5:] == attribute:
            entity_id = "user"
        # 去重：同一 (实体, 属性) 的当前值完全相同 → 直接返回已有，不重复写
        same_current = list(
            self.db.scalars(
                select(Fact).where(
                    Fact.entity_id == entity_id,
                    Fact.attribute == attribute,
                    Fact.valid_to.is_(None),
                )
            )
        )
        for f in same_current:
            if f.value.strip() == value.strip():
                return f

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
        supersedes_id: str | None = None
        if old is not None:
            if valid_from >= old.valid_from:
                # 新值更晚或同时：旧事实失效（不删除），有效区间截止到新值生效时刻
                old.valid_to = valid_from
                supersedes_id = old.id
            else:
                # 乱序补写更早的事实：插入为历史区间，不改变当前值；
                # 该历史事实的有效期截止到当前事实的生效时间。
                supersedes_id = None
        # attribute 名变了（如 5K_personal_best → 5K 最好成绩（PB）→ 5k_pb）：
        # 同一实体下共享关键词的当前值视为「同一属性的更新」，自动失效（历史保留）。
        new_tokens = _attr_tokens(attribute)
        if new_tokens:
            others = list(
                self.db.scalars(
                    select(Fact).where(Fact.entity_id == entity_id, Fact.valid_to.is_(None))
                )
            )
            for cand in others:
                if old is not None and cand.id == old.id:
                    continue
                if cand.value == value:
                    continue
                if _attr_tokens(cand.attribute) & new_tokens:
                    cand.valid_to = valid_from
                    supersedes_id = supersedes_id or cand.id

        fact = Fact(
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            valid_from=valid_from,
            valid_to=(old.valid_from if old is not None and valid_from < old.valid_from else None),
            source_session_id=source_session_id,
            source_message_id=source_message_id,
            confidence=confidence,
            fact_type=fact_type,
            conflict_type=conflict_type,
            supersedes_id=supersedes_id,
        )
        self.db.add(fact)
        self.db.flush()
        # 容量保护：超出每实体当前值上限时，自动把最旧/最低置信度的值标记失效（归档可追溯）
        self.last_archived = self._enforce_capacity(entity_id, valid_from)
        return fact

    def _enforce_capacity(self, entity_id: str, now: datetime) -> int:
        """把超出上限的当前值标记失效；优先归档置信度低、其次最旧的。返回归档条数。"""
        limit = self.max_current_per_entity
        if not limit or limit <= 0:
            return 0
        current = list(
            self.db.scalars(
                select(Fact).where(Fact.entity_id == entity_id, Fact.valid_to.is_(None))
            )
        )
        excess = len(current) - limit
        if excess <= 0:
            return 0
        current.sort(key=lambda f: (f.confidence, f.valid_from))
        for f in current[:excess]:
            f.valid_to = now
        self.db.flush()
        return excess

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

    def forget(self, entity_id: str, attribute: str, at: datetime | None = None) -> Fact | None:
        """标记当前值为失效（不物理删除，保留历史）。

        与 tools.py 的 memory_forget 同语义；这里补 commit，供 API 直接调用。
        返回被失效的事实；不存在当前值时返回 None。
        """
        cur = self.current(entity_id, attribute)
        if cur is None:
            return None
        cur.valid_to = at or datetime.now(timezone.utc)
        self.db.commit()
        return cur

    def search_text(self, query: str, limit: int = 20) -> list[Fact]:
        """确定性文本检索：按空白/标点分词，多 token OR LIKE，命中越多越靠前。

        改进前是整串 LIKE（`%25:50 成绩%` 这种永远不命中），导致 agent 找不到旧记录；
        这里先分词再逐 token 匹配，当前值优先返回。
        """
        tokens = [t for t in re.split(r"[\s,;，。；、:：\-_/（）()]+", query or "") if t]
        tokens = [t for t in tokens if t][:8]
        if not tokens:
            return []
        cond = None
        for t in tokens:
            like = f"%{t}%"
            c = Fact.attribute.like(like) | Fact.value.like(like) | Fact.entity_id.like(like)
            cond = c if cond is None else (cond | c)
        rows = list(
            self.db.scalars(
                select(Fact).where(cond).order_by(Fact.valid_from.desc()).limit(max(limit * 3, 60))
            )
        )

        def _score(f: Fact) -> int:
            text = f"{f.entity_id} {f.attribute} {f.value}".lower()
            return sum(1 for t in tokens if t.lower() in text)

        # 当前值优先，其次命中 token 数多者，再次新者
        rows.sort(key=lambda f: (0 if f.valid_to is None else 1, -_score(f), -f.valid_from.timestamp()))
        return rows[:limit]
