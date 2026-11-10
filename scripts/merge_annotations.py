# -*- coding: utf-8 -*-
"""合并人工标注进 ku72.jsonl，并输出分母台账。

来源：
  dataset/v1/annotations-pilot10-v2.jsonl     9 行（pilot10，v3 回填；abs 行忽略）
  dataset/v1/annotations-remaining-fixed.jsonl 63 行（v3.1 修正版）
目标：
  data/annotations/ku72.jsonl                 72 行（完整标注）
  data/annotations/ku72_denominators.json     分母台账（可入库）

规则：
  - 只覆盖 v3 字段，丢弃 question（题目文本不入库）
  - current 63 / retrospective 9 / manual 0（预期）
  - 过期事实率有效分母 = current − placeholder − null_stale
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KU72 = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
PILOT = os.path.join(ROOT, "dataset", "v1", "annotations-pilot10-v2.jsonl")
FIXED = os.path.join(ROOT, "dataset", "v1", "annotations-remaining-fixed.jsonl")
OUT_DENOM = os.path.join(ROOT, "data", "annotations", "ku72_denominators.json")

FIELDS = [
    "question_id", "query_form", "new_value", "official_answer", "official_answer_role",
    "official_answer_session_index", "stale_value", "stale_value_is_placeholder",
    "stale_source_session_id", "new_source_session_id", "session_order_source",
    "gold_session_index", "is_abstention", "conflict_type", "expected_resolution",
    "entity", "match_mode", "note",
]


def load_jsonl(p):
    return [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]


def main() -> int:
    ku72 = load_jsonl(KU72)
    pilot = load_jsonl(PILOT)
    fixed = load_jsonl(FIXED)
    overrides: dict[str, dict] = {}
    for r in pilot:
        if r.get("is_abstention"):
            continue
        overrides[r["question_id"]] = r
    for r in fixed:
        overrides[r["question_id"]] = r

    merged = []
    for row in ku72:
        qid = row["question_id"]
        if qid in overrides:
            src = overrides[qid]
            new = {k: src.get(k, row.get(k)) for k in FIELDS}
            new["question_id"] = qid
            merged.append(new)
        else:
            merged.append({k: row.get(k) for k in FIELDS})

    # 断言：72 行、无重复、全部非空 query_form
    ids = [r["question_id"] for r in merged]
    assert len(merged) == 72, len(merged)
    assert len(set(ids)) == 72, "duplicate ids"
    for r in merged:
        if r["query_form"] not in {"current", "retrospective", "manual_needed", "abstention"}:
            print("BAD", r["question_id"], r["query_form"])
            return 1

    with open(KU72, "w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    cnt = Counter(r["query_form"] for r in merged)
    current = [r for r in merged if r["query_form"] == "current"]
    retro = [r for r in merged if r["query_form"] == "retrospective"]
    placeholder = [r["question_id"] for r in current if r.get("stale_value_is_placeholder")]
    null_stale = [r["question_id"] for r in current if r.get("stale_value") is None]
    stale_eff = len(current) - len(placeholder) - len(null_stale)

    denom = {
        "n_total": len(merged),
        "by_query_form": dict(cnt),
        "layer_1a_current": len(current),
        "layer_1b_retrospective": len(retro),
        "layer_1c_abstention": 6,
        "stale_value_placeholder_ids": placeholder,
        "stale_value_null_ids": null_stale,
        "stale_fact_rate_denominator": stale_eff,
        "note": "1a 与协议一致率分母=63；过期事实率有效分母=1a − placeholder − null_stale",
    }
    with open(OUT_DENOM, "w", encoding="utf-8") as f:
        json.dump(denom, f, ensure_ascii=False, indent=2)

    print(json.dumps(denom, ensure_ascii=False, indent=2))
    print("merged ->", KU72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
