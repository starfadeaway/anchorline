# -*- coding: utf-8 -*-
"""A/A 噪声底 pilot：B 臂（官方基线）20 题 × N=10，真实温度 / 真实检索。

口径（v0.8 §6.1）：
  - A/A 只在 pilot 20 题上跑 N=10，不进 M3 主矩阵；
  - 记录每题 10 次的主指标值，取**配对差值的平均绝对值与最大值**作噪声底；
  - 不关温度（关了噪声底趋近 0，后续差异会被误判成提升）。

用法：
  .venv\\Scripts\\python.exe scripts\\aa_pilot.py [--n 10] [--limit 20] [--temp 1.0]
输出：data/eval/aa_pilot.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
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

V2 = os.path.join(ROOT, "dataset", "v2")
OUT = os.path.join(ROOT, "data", "eval")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    # B/D 臂共用同一抽样函数，保证同题
    sample = sample_deterministic(limit=args.limit, seed=args.seed)
    print(f"pilot {len(sample)} 题；N={args.n}；temp={args.temp}")

    tbl = open_table("v2_web_slices")
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    os.makedirs(OUT, exist_ok=True)
    results = []
    t0 = time.time()
    for qi, q in enumerate(sample, 1):
        scores = []
        ctx_tokens = []
        for _ in range(args.n):
            r = answer_baseline(reader, embedder, tbl, q["question"], temperature=args.temp)
            s = score_deterministic(r.answer, q.get("answer"), q["eval_function"])
            scores.append(1 if s else 0)
            ctx_tokens.append(r.context_tokens)
        span = max(scores) - min(scores)
        results.append({
            "question_id": q["id"],
            "eval_function": q["eval_function"].split("|")[0],
            "scores": scores,
            "span": span,
            "mean": statistics.mean(scores),
            "context_tokens_mean": int(statistics.mean(ctx_tokens)),
        })
        print(f"  [{qi}/{len(sample)}] {q['id']} scores={scores} span={span} ctx≈{int(statistics.mean(ctx_tokens))}t {time.time()-t0:.0f}s")

    # 配对差：同题 10 次中所有两两组合
    diffs = []
    for r in results:
        s = r["scores"]
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                diffs.append(abs(s[i] - s[j]))
    nonzero = sum(1 for d in diffs if d > 0)

    summary = {
        "config": {
            "arm": "B_official_raw_state_slice",
            "reader_model": Settings().deepseek_reader_model,
            "embedding_model": Settings().siliconflow_embedding_model,
            "temperature": args.temp,
            "n_per_question": args.n,
            "questions": len(results),
            "top_k": 6,
        },
        "noise_floor": {
            "pairwise_abs_diff_mean": statistics.mean(diffs) if diffs else 0.0,
            "pairwise_abs_diff_max": max(diffs) if diffs else 0.0,
            "nonzero_pairs": nonzero,
            "pairs_total": len(diffs),
            "question_span_mean": statistics.mean(r["span"] for r in results),
            "question_span_max": max((r["span"] for r in results), default=0),
        },
        "per_question": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    path = os.path.join(OUT, "aa_pilot.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("=== A/A noise floor ===")
    print(json.dumps(summary["noise_floor"], ensure_ascii=False, indent=1))
    print("saved:", path)


if __name__ == "__main__":
    main()
