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

from sqlalchemy import delete, select, update  # noqa: E402

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
        # 清旧种子（先解除自引用外键，再删）
        demo_ids = [f.id for f in db.scalars(select(Fact).where(Fact.entity_id == ENTITY)).all()]
        if demo_ids:
            db.execute(update(Fact).where(Fact.supersedes_id.in_(demo_ids)).values(supersedes_id=None))
            db.execute(delete(Fact).where(Fact.id.in_(demo_ids)))
            db.commit()
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

        # 会话 + 消息（user 首条带 [demo] 标记用于幂等清理；assistant 写自然回复，不带头缀）
        session_ids = []
        scripts = {
            "跑步": [
                ("user", "[demo] 我最近在练 5K，想突破 23 分钟"),
                ("assistant", "记下了：你目前 5K PB 是 23:50，目标是 23:00。建议先用 5:00–5:05/km 的配速做 4×800 米间歇，每周两次，中间留一天轻松跑恢复；先把 23:30 当第一个小目标。"),
            ],
            "游泳": [
                ("user", "[demo] 我 200 米自由泳最好成绩是 2 分 15 秒"),
                ("assistant", "收到，200 米自由泳 2:15 已经不错。想冲 2:05，核心是把划频稳定在 38–40 次/分、每 50 米控制在 32 秒左右；先练 8×50 米主项间歇，组间 20 秒。"),
            ],
            "乒乓球": [
                ("user", "[demo] 我打乒乓球已经连胜 5 个对手了"),
                ("assistant", "厉害，五连胜说明你的正手和发球在业余里已经够用。想继续涨球，可以找水平高半档的球友打，输几场比一直赢更能暴露脚步和接发球的问题。"),
            ],
            "饮食": [
                ("user", "[demo] 我口味清淡，少油少盐"),
                ("assistant", "明白，清淡少油少盐。那给你配餐时我会避开重口和油炸，优先蒸煮、凉拌；蛋白质用鸡胸/鱼虾/豆制品，主食可以粗细搭配。"),
            ],
            "工作": [
                ("user", "[demo] 我在做 Anchorline 记忆层这个项目"),
                ("assistant", "记住了：你在做 Anchorline 记忆层，同时在桥接 LoreKeeper 知识库。需要我帮你把「记忆写入 → 检索召回 → 冲突裁决」这条链路整理成可演示的步骤吗？"),
            ],
            "旅行": [
                ("user", "[demo] 十一打算去云南玩"),
                ("assistant", "好，十一去云南。这个时间人流大，建议提前订大理/丽江的住宿；如果只有 5 天，昆明—大理—丽江一线就够，别贪多。要路线的话我可以按你的天数排。"),
            ],
        }
        sessions_by_topic: dict[str, str] = {}
        for topic, msgs in scripts.items():
            s = ChatSession(domain="chat", topic=topic, created_at=now - timedelta(days=3))
            db.add(s)
            db.flush()
            sessions_by_topic[topic] = s.id
            for role, content in msgs:
                db.add(Message(session_id=s.id, role=role, content=content))
            db.add(
                Trace(
                    session_id=s.id,
                    query=msgs[0][1][:200],
                    budget_tokens=4000,
                    used_tokens=180,
                    layers="demo>seed;steps=1",
                    injected_fact_ids=json.dumps([], ensure_ascii=False),
                    recalls=json.dumps([], ensure_ascii=False),
                    resolution="done",
                )
            )
            session_ids.append(s.id)

        # 事实（走 FactStore：supersede + 容量 + 索引同步）
        store = FactStore(db)
        facts = [
            ("5k_pb", "27:12", 180, "跑步"),
            ("5k_pb", "24:30", 90, "跑步"),
            ("5k_pb", "23:50", 30, "跑步"),
            ("200米游泳最好成绩", "2分15秒", 60, "游泳"),
            ("饮食偏好", "喜欢清淡，少油少盐", 30, "饮食"),
            ("咖啡习惯", "每天两杯手冲", 20, "饮食"),
            ("工作项目", "Anchorline 记忆层", 120, "工作"),
            ("工作项目", "LoreKeeper 知识库桥接", 15, "工作"),
            ("旅行计划", "十一去云南", 10, "旅行"),
        ]
        for attr, value, days_ago, topic in facts:
            store.write(
                entity_id=ENTITY,
                attribute=attr,
                value=value,
                valid_from=now - timedelta(days=days_ago),
                source_session_id=sessions_by_topic.get(topic),
            )
        db.commit()

        # 演示：5k_pb 保留最新（旧值已自动失效，但裁决记录里列出旧值以便追溯）
        db.commit()
        same_attr = list(db.scalars(select(Fact).where(Fact.entity_id == ENTITY, Fact.attribute == "5k_pb")).all())
        kept = max(same_attr, key=lambda f: f.valid_from) if same_attr else None
        if kept:
            old_ids = [f.id for f in same_attr if f.id != kept.id]
            db.add(
                ReviewDecision(
                    entity_id=ENTITY,
                    attribute="5k_pb",
                    kept_fact_id=kept.id,
                    invalidated_fact_ids=json.dumps(old_ids, ensure_ascii=False),
                    reason="demo: 保留最新 PB（旧值已自动失效）",
                    operator="seed",
                )
            )
        # 演示冲突（3 组）：直接用 ORM 造 current 事实（绕过 write 的自动失效），
        # 2 组自动裁决（进“裁决历史”），1 组留作待裁决（审核页可操作）
        def make_pair(attr_a: str, value_a: str, attr_b: str, value_b: str, days: int, source: str | None = None):
            a = Fact(
                entity_id=ENTITY, attribute=attr_a, value=value_a,
                valid_from=now - timedelta(days=days), source_session_id=source,
            )
            b = Fact(
                entity_id=ENTITY, attribute=attr_b, value=value_b,
                valid_from=now - timedelta(days=max(0, days - 2)), source_session_id=source,
            )
            db.add_all([a, b])
            db.flush()
            return a, b

        def decide(kept_fact, invalidated, reason: str) -> None:
            for f in invalidated:
                f.valid_to = now
            db.add(
                ReviewDecision(
                    entity_id=ENTITY,
                    attribute=kept_fact.attribute,
                    kept_fact_id=kept_fact.id,
                    invalidated_fact_ids=json.dumps([f.id for f in invalidated], ensure_ascii=False),
                    reason=reason,
                    operator="seed",
                )
            )

        a1, b1 = make_pair("跑步 配速", "5:30/km", "跑步 目标配速", "5:00/km", 20, sessions_by_topic.get("跑步"))
        decide(a1, [b1], "demo: 保留实测配速，目标配速作废")
        a2, b2 = make_pair("饮食 偏好", "清淡少油", "饮食 禁忌", "不吃辣", 15, sessions_by_topic.get("饮食"))
        decide(b2, [a2], "demo: 保留禁忌（更严格）")
        make_pair("工作 项目", "Anchorline 记忆层", "工作 目标", "写完 M3 主实验", 5, sessions_by_topic.get("工作"))  # 留待裁决

        db.commit()
        print(f"seeded: facts(user:demo) + {len(session_ids)} sessions + traces + 3 conflicts (2 decided, 1 pending)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
