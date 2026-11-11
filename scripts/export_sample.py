# -*- coding: utf-8 -*-
"""生成脱敏的示例导出（data/exports/sample/，可入库）。

内容全部是演示文本，不含真实聊天记录；结构对齐 scripts/export_db.py 的 6 表 JSONL + summary。
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "exports", "sample")

FACTS = [
    {"id": "f00000000000000000000000000001", "entity_id": "user", "attribute": "5K 最好成绩", "value": "25:50（日期 2023-05-30）", "valid_from": "2023-05-30T00:00:00", "valid_to": "2026-11-09T21:45:00", "confidence": 1.0, "supersedes_id": None, "fact_type": "semantic", "conflict_type": None, "source_session_id": None, "source_message_id": None},
    {"id": "f00000000000000000000000000002", "entity_id": "user", "attribute": "5K 最好成绩", "value": "23:50", "valid_from": "2026-11-09T21:45:00", "valid_to": None, "confidence": 1.0, "supersedes_id": "f00000000000000000000000000001", "fact_type": "semantic", "conflict_type": "时效", "source_session_id": "s00000000000000000000000000001", "source_message_id": 2},
    {"id": "f00000000000000000000000000003", "entity_id": "user", "attribute": "200米游泳最好成绩", "value": "2分15秒", "valid_from": "2026-11-09T21:48:47", "valid_to": None, "confidence": 1.0, "supersedes_id": None, "fact_type": "semantic", "conflict_type": None, "source_session_id": None, "source_message_id": None},
    {"id": "f00000000000000000000000000004", "entity_id": "user", "attribute": "饮食偏好", "value": "清淡少油少盐", "valid_from": "2026-11-09T21:50:00", "valid_to": None, "confidence": 1.0, "supersedes_id": None, "fact_type": "semantic", "conflict_type": None, "source_session_id": None, "source_message_id": None},
    {"id": "f00000000000000000000000000005", "entity_id": "user.猫", "attribute": "名字", "value": "豆豆", "valid_from": "2026-11-10T23:22:18", "valid_to": None, "confidence": 1.0, "supersedes_id": None, "fact_type": "semantic", "conflict_type": None, "source_session_id": "s00000000000000000000000000002", "source_message_id": 4},
    {"id": "f00000000000000000000000000006", "entity_id": "大模型.示例模型", "attribute": "模型身份", "value": "演示用大模型实体（非真实用户）", "valid_from": "2026-11-10T23:40:29", "valid_to": None, "confidence": 1.0, "supersedes_id": None, "fact_type": "semantic", "conflict_type": None, "source_session_id": None, "source_message_id": None},
]

SESSIONS = [
    {"id": "s00000000000000000000000000001", "domain": "chat", "topic": "跑步记录", "created_at": "2026-11-09T21:44:00"},
    {"id": "s00000000000000000000000000002", "domain": "chat", "topic": "宠物", "created_at": "2026-11-10T23:22:00"},
    {"id": "s00000000000000000000000000003", "domain": "chat", "topic": "模型与配置", "created_at": "2026-11-10T23:40:00"},
]

MESSAGES = [
    {"id": 1, "session_id": "s00000000000000000000000000001", "role": "user", "content": "记住我的 5K 最好成绩是 25:50（日期 2023-05-30）", "created_at": "2026-11-09T21:44:10"},
    {"id": 2, "session_id": "s00000000000000000000000000001", "role": "assistant", "content": "已记下：5K 最好成绩 25:50（2023-05-30）。", "created_at": "2026-11-09T21:44:30"},
    {"id": 3, "session_id": "s00000000000000000000000000002", "role": "user", "content": "我家的猫叫豆豆", "created_at": "2026-11-10T23:22:05"},
    {"id": 4, "session_id": "s00000000000000000000000000002", "role": "assistant", "content": "已记下：你的猫叫豆豆。", "created_at": "2026-11-10T23:22:30"},
    {"id": 5, "session_id": "s00000000000000000000000000003", "role": "user", "content": "大肥鱼是大模型的爱称，单独分组", "created_at": "2026-11-10T23:40:05"},
    {"id": 6, "session_id": "s00000000000000000000000000003", "role": "assistant", "content": "好，已归入「模型与配置」分组。", "created_at": "2026-11-10T23:40:30"},
]

TRACES = [
    {"id": 1, "session_id": "s00000000000000000000000000001", "query": "记住我的 5K 最好成绩是 25:50", "budget_tokens": 4000, "used_tokens": 180, "layers": "chat>tools;steps=2", "injected_fact_ids": "[]", "resolution": "done", "recalls": "[]", "created_at": "2026-11-09T21:44:30"},
    {"id": 2, "session_id": "s00000000000000000000000000002", "query": "我家的猫叫豆豆", "budget_tokens": 4000, "used_tokens": 120, "layers": "chat>tools;steps=1", "injected_fact_ids": "[]", "resolution": "done", "recalls": "[]", "created_at": "2026-11-10T23:22:30"},
]

EVAL_RUNS = [
    {"id": "e00000000000000000000000000001", "benchmark": "v2-web", "arm": "B", "budget_tokens": 4000, "question_id": "q0001", "score": 0.0, "scoring_mode": "deterministic", "reader_model": "deepseek-flash", "judge_model": None, "judge_prompt_sha256": None, "config_hash": "demo"},
    {"id": "e00000000000000000000000000002", "benchmark": "v2-web", "arm": "D", "budget_tokens": 4000, "question_id": "q0001", "score": 1.0, "scoring_mode": "deterministic", "reader_model": "deepseek-flash", "judge_model": None, "judge_prompt_sha256": None, "config_hash": "demo"},
]

DECISIONS = [
    {"id": "r0000000000000000000000000000001", "entity_id": "user", "attribute": "5K 最好成绩", "kept_fact_id": "f00000000000000000000000000002", "invalidated_fact_ids": ["f00000000000000000000000000001"], "reason": "保留最新 PB", "operator": "human", "created_at": "2026-11-09T21:45:00"},
]


def write_jsonl(name: str, rows: list[dict]) -> None:
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    write_jsonl("facts.jsonl", FACTS)
    write_jsonl("sessions.jsonl", SESSIONS)
    write_jsonl("messages.jsonl", MESSAGES)
    write_jsonl("traces.jsonl", TRACES)
    write_jsonl("eval_runs.jsonl", EVAL_RUNS)
    write_jsonl("review_decisions.jsonl", DECISIONS)
    summary = {
        "exported_at": "2026-11-11T16:00:00",
        "note": "脱敏示例导出（全部为演示文本，不含真实聊天记录）",
        "tables": {"facts": len(FACTS), "sessions": len(SESSIONS), "messages": len(MESSAGES),
                   "traces": len(TRACES), "eval_runs": len(EVAL_RUNS), "review_decisions": len(DECISIONS)},
    }
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(f"sample export written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
