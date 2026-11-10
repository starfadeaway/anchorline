# -*- coding: utf-8 -*-
"""演示数据种子：生成 user:demo 的事实（含历史）、6 个会话、trace 与裁决记录。

幂等：每次先清掉 user:demo 的 facts / sessions / traces / review_decisions，再重建。
用法：.venv\\Scripts\\python.exe scripts/seed_demo.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from sqlalchemy import delete, select  # noqa: E402

from anchorline.db import session_factory  # noqa: E402
from anchorline.memory.store import FactStore  # noqa: E402
from anchorline.models import Fact, Message, ReviewDecision, Trace  # noqa: E402
from anchorline.models import Session as ChatSession

ENTITY = "user:demo"
TOPICS = ["跑步", "游泳", "乒乓球", "饮食", "工作", "旅行"]


def main() -> int:
    db = session_factory()()
    now = datetime.now()
    try:
        # 清旧种子
        db.execute(delete(Fact).where(Fact.entity_id == ENTITY))
        old_sessions = list(db.scalars(select(ChatSession).where(ChatSession.topic.in_(TOPICS))).all())
        # 只删 topic 在演示集合且无真实消息的会话（避免误删用户真实数据）
        demo_sessions = []
        for s in old_sessions:
            first = db.scalars(select(Message).where(Message.session_id == s.id).limit(1)).first()
            if first and first.content.startswith("[demo]"):
                demo_sessions.append(s.id)
        if demo_sessions:
            db.execute(delete(Message).where(Message.session_id.in_(demo_sessions)))
            db.execute(delete(Trace).where(Trace.session_id.in_(demo_sessions)))
            db.execute(delete(ChatSession).where(ChatSession.id.in_(demo_sessions)))
        db.execute(delete(ReviewDecision).where(ReviewDecision.entity_id == ENTITY))
        db.commit()

        # 事实（走 FactStore：supersede + 容量 + 索引同步）
        store = FactStore(db)
        facts = [
            ("5k_pb", "27:12", 180),
            ("5k_pb", "24:30", 90),
            ("5k_pb", "23:50", 30),
            ("200米游泳最好成绩", "2分15秒", 60),
            ("乒乓球经历", "连续打赢过5个对手（连胜5人）", 45),
            ("饮食偏好", "喜欢清淡，少油少盐", 30),
            ("咖啡习惯", "每天两杯手冲", 20),
            ("工作项目", "Anchorline 记忆层", 120),
            ("工作项目", "LoreKeeper 知识库桥接", 15),
            ("旅行计划", "十一去云南", 10),
        ]
        for attr, value, days_ago in facts:
            store.write(entity_id=ENTITY, attribute=attr, value=value, valid_from=now - timedelta(days=days_ago))
        db.commit()

        # 会话 + 消息
        session_ids = []
        scripts = {
            "跑步": ["[demo] 我最近在练 5K，想突破 23 分钟", "[demo] 我目前 PB 是 23:50，目标是 23:00"],
            "游泳": ["[demo] 我 200 米自由泳最好成绩是 2 分 15 秒", "[demo] 想练到 2 分 05 秒"],
            "乒乓球": ["[demo] 我打乒乓球已经连胜 5 个对手了", "[demo] 打算找水平更高的球友练"],
            "饮食": ["[demo] 我口味清淡，少油少盐", "[demo] 平时喜欢自己做饭"],
            "工作": ["[demo] 我在做 Anchorline 记忆层这个项目", "[demo] 也在桥接 LoreKeeper 知识库"],
            "旅行": ["[demo] 十一打算去云南玩", "[demo] 还没定具体路线"],
        }
        for topic, msgs in scripts.items():
            s = ChatSession(domain="chat", topic=topic, created_at=now - timedelta(days=3))
            db.add(s)
            db.flush()
            for i, content in enumerate(msgs):
                db.add(Message(session_id=s.id, role="user" if i % 2 == 0 else "assistant", content=content))
            db.add(
                Trace(
                    session_id=s.id,
                    query=msgs[0][:200],
                    budget_tokens=4000,
                    used_tokens=180,
                    layers="demo>seed;steps=1",
                    injected_fact_ids=json.dumps([], ensure_ascii=False),
                    recalls=json.dumps([], ensure_ascii=False),
                    resolution="done",
                )
            )
            session_ids.append(s.id)

        # 裁决（演示：user:demo 的两条 5k_pb 历史选保留）
        db.commit()
        kept = db.scalars(select(Fact).where(Fact.entity_id == ENTITY, Fact.attribute == "5k_pb").order_by(Fact.valid_from.desc()).limit(1)).first()
        if kept:
            db.add(
                ReviewDecision(
                    entity_id=ENTITY,
                    attribute="5k_pb",
                    kept_fact_id=kept.id,
                    invalidated_fact_ids=json.dumps([], ensure_ascii=False),
                    reason="demo: 保留最新 PB",
                    operator="seed",
                )
            )
        db.commit()
        print(f"seeded: facts(user:demo) + {len(session_ids)} sessions + traces + 1 decision")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
