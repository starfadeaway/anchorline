# -*- coding: utf-8 -*-
"""pilot10 标注回填与校验（schema v3）。

为每行补：
  - official_answer：官方 answer 原样（只读）
  - official_answer_role：current / old / null
  - official_answer_session_index：0/1/null（官方 answer 所在 gold session）
  - stale_value_is_placeholder：bool
并做一致性校验：
  - question_id 唯一；query_form 合法
  - is_abstention 与 `_abs` 后缀一致
  - 非 abs 题的 stale/new source 必须属于 answer_session_ids
  - retrospective 题：official_answer 应等于 stale_value；current 题：official_answer 与 new_value 归一化后应一致
输出：dataset/v1/annotations-pilot10-v2.jsonl（含 session 片段，**不入库**）
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "dataset", "v1", "annotations-pilot10.jsonl")
OUT = os.path.join(ROOT, "dataset", "v1", "annotations-pilot10-v2.jsonl")
KU = os.path.join(ROOT, "dataset", "longmemeval_s_cleaned.json")

PLACEHOLDER = {"5a4f22c0"}


def norm(s: object) -> str:
    return " ".join(str(s or "").lower().replace("-", " ").replace("_", " ").split())


def main() -> int:
    ku = json.load(open(KU, encoding="utf-8"))
    qs = {q["question_id"]: q for q in ku if q.get("question_type") == "knowledge-update"}
    rows = [json.loads(line) for line in open(SRC, encoding="utf-8") if line.strip()]
    errors: list[str] = []
    seen: set[str] = set()

    for r in rows:
        qid = r["question_id"]
        if qid in seen:
            errors.append(f"{qid}: duplicate question_id")
        seen.add(qid)
        q = qs.get(qid)
        if q is None:
            errors.append(f"{qid}: not a knowledge-update question")
            continue

        if r["query_form"] not in {"current", "retrospective", "abstention", "manual_needed"}:
            errors.append(f"{qid}: bad query_form {r['query_form']}")
        if r["is_abstention"] != qid.endswith("_abs"):
            errors.append(f"{qid}: is_abstention mismatch")

        r["official_answer"] = q.get("answer")
        if r["query_form"] == "retrospective":
            r["official_answer_role"] = "old"
            r["official_answer_session_index"] = 0
        elif r["query_form"] == "current":
            r["official_answer_role"] = "current"
            r["official_answer_session_index"] = 1
        else:
            r["official_answer_role"] = None
            r["official_answer_session_index"] = None
        r["stale_value_is_placeholder"] = qid in PLACEHOLDER

        if not r["is_abstention"]:
            gold = list(q.get("answer_session_ids") or [])
            for key in ("stale_source_session_id", "new_source_session_id"):
                if r.get(key) not in gold:
                    errors.append(f"{qid}: {key}={r.get(key)} not in {gold}")
            if r["gold_session_index"] not in (0, 1):
                errors.append(f"{qid}: gold_session_index={r['gold_session_index']}")

            if r["query_form"] == "retrospective":
                if norm(r["stale_value"]) not in norm(q.get("answer")):
                    errors.append(f"{qid}: retrospective stale_value != official answer")
            elif r["query_form"] == "current":
                if norm(r["new_value"]) not in norm(q.get("answer")):
                    errors.append(f"{qid}: current new_value != official answer")

    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"rows={len(rows)} -> {OUT}")
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print("  -", e)
        return 1
    print("validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
