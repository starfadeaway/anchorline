# -*- coding: utf-8 -*-
"""诊断：为什么 154 题准确率这么低？

抽 10 道题跑一次 B 臂（官方基线），保存答案与判分，人工看：
  - 是「检索没命中正确轨迹」？
  - 是「4k 预算截断丢证据」？
  - 还是「答案近似但判分严格」？

输出：data/eval/diag_b_10.json（含 answer 文本，本地）
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.config import Settings  # noqa: E402
from anchorline.evaluation.baseline_arm import answer_baseline  # noqa: E402
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import sample_deterministic  # noqa: E402
from anchorline.llm import embedding_client, reader_client  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

OUT = os.path.join(ROOT, "data", "eval", "diag_b_10.json")


def main() -> int:
    sample = sample_deterministic(limit=10, seed=7)  # 与 154 不同种子，抽 10 道
    tbl = open_table("v2_web_slices")
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    rows = []
    for q in sample:
        r = answer_baseline(reader, embedder, tbl, q["question"], temperature=1.0)
        s = score_deterministic(r.answer, q.get("answer"), q["eval_function"])
        rows.append({
            "question_id": q["id"],
            "type": q.get("question_type"),
            "question": q["question"],
            "gold": q.get("answer"),
            "eval": q["eval_function"].split("|")[0],
            "answer": r.answer,
            "score": 1 if s else 0,
            "ctx_tokens": r.context_tokens,
            "top_hit": (r.hits[0]["traj_id"] if r.hits else None),
            "top_sim": round(1 - float(r.hits[0].get("_distance") or 0), 3) if r.hits else None,
        })
        print(f"[{q['id']}] score={1 if s else 0} | gold={str(q.get('answer'))[:80]!r}")
        print(f"    answer: {r.answer[:200]!r}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("written:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
