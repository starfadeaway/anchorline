# -*- coding: utf-8 -*-
"""B 臂（a11y 子集基线）评测：与 C1/C2/D 同一批题、同一 reader、同一预算。

此前 B 的 154 题产物来自一次性脚本（仓库里没有可复跑的入口）；
本脚本补上入口，便于索引重建后重跑 B 与 168。

用法：
  .venv\\Scripts\\python.exe scripts\\eval_b_arm.py --limit 154 --out data/eval/b_arm_154_run3.json
默认输出到 data/eval/_drafts/（不覆盖已入库产物）。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.config import Settings  # noqa: E402
from anchorline.evaluation.baseline_arm import answer_baseline  # noqa: E402
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import sample_deterministic  # noqa: E402
from anchorline.llm import embedding_client, reader_client  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

TABLE = "v2_web_slices"
OUT_DEFAULT = os.path.join(ROOT, "data", "eval", "_drafts", "b_arm_154.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=154, help="题数（154 = 全部确定性题）")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--table", default=TABLE)
    ap.add_argument("--out", default=None, help="结果 JSON（默认 data/eval/_drafts/b_arm_154.json）")
    args = ap.parse_args()
    out_json = args.out or OUT_DEFAULT
    os.makedirs(os.path.dirname(out_json), exist_ok=True)

    sample = sample_deterministic(limit=args.limit, seed=args.seed)
    tbl = open_table(args.table)
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    results = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        r = answer_baseline(reader, embedder, tbl, q["question"], temperature=args.temperature)
        s = score_deterministic(r.answer, q.get("answer"), q["eval_function"])
        score = 1 if s else 0
        results.append(
            {
                "question_id": q["id"],
                "scores": [score],
                "mean": score,
                "context_tokens_mean": r.context_tokens,  # V3：与旧 B 产物字段名一致
                "dropped": r.dropped_slices,  # V3：统一叫 dropped（旧产物无此字段）
            }
        )
        print(f"  [{i}/{len(sample)}] {q['id']} score={score} ctx={r.context_tokens} dropped={r.dropped_slices} {time.time()-t0:.0f}s")

    summary = {
        "config": {
            "arm": "B_a11y_subset_baseline",
            "reader_model": Settings().deepseek_reader_model,
            "embedding_model": Settings().siliconflow_embedding_model,
            "temperature": args.temperature,
            "budget_tokens": 4000,
            "top_k": 6,
            "n_questions": len(results),
            "table": args.table,
        },
        "accuracy": statistics.mean([r["mean"] for r in results]) if results else None,
        "per_question": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)
    print(f"written: {out_json}  n={len(results)}  accuracy={summary['accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
