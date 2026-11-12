# -*- coding: utf-8 -*-
"""C1 臂（完整轨迹 × 官方切片）评测入口。

此前 C1 只有索引构建脚本、没有可复跑入口（评审 42.1 的衍生缺口）。
C1 索引字段是 `text/state_index`（B 用 `state_blocks/center`），所以这里做字段适配。

用法：
  .venv\\Scripts\\python.exe scripts\\eval_c1_arm.py --limit 154 --out data/eval/_drafts/c1_arm_154.json
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
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import sample_deterministic  # noqa: E402
from anchorline.evaluation.reader import build_messages  # noqa: E402
from anchorline.llm import embedding_client, reader_client  # noqa: E402
from anchorline.memory.l3 import assemble_blocks  # noqa: E402
from anchorline.retrieval.baseline import format_query_for_embedding, normalize_vector  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

TABLE = "v2_web_states_c1"
OUT_DEFAULT = os.path.join(ROOT, "data", "eval", "_drafts", "c1_arm_154.json")


def run_one(reader, embedder, tbl, question: str, budget: int = 4000) -> tuple[str, int, int]:
    qv = normalize_vector(embedder.embed([format_query_for_embedding(question)])[0])
    hits = tbl.search(qv).limit(6).to_list()
    items: list[tuple[float, str]] = []
    for h in hits:
        sim = 1.0 - float(h.get("_distance") or 0.0)
        text = h.get("state_blocks") or h.get("text") or ""
        idx = h.get("center", h.get("state_index", ""))
        block = (
            f"### Raw state result\n"
            f"- Trajectory: {h.get('traj_id', '')}\n"
            f"- Goal: {h.get('goal', '')}\n"
            f"- Center state index: {idx}\n"
            f"- Similarity (1 − L2 距离，非余弦): {sim:.4f}\n\n"
            f"Relevant state slices\n{text}\n"
        )
        items.append((sim, block))
    context, used_tokens, dropped = assemble_blocks(items, budget)
    messages = build_messages(question, context or "(empty)")
    answer = reader.complete(messages, temperature=1.0, max_tokens=8192)
    if not answer.strip():
        answer = reader.complete(messages, temperature=1.0, max_tokens=16384)
    return answer, used_tokens, dropped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=154)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--table", default=TABLE)
    ap.add_argument("--out", default=None)
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
        answer, ctx_tokens, dropped = run_one(reader, embedder, tbl, q["question"])
        s = score_deterministic(answer, q.get("answer"), q["eval_function"])
        score = 1 if s else 0
        results.append(
            {
                "question_id": q["id"],
                "scores": [score],
                "mean": score,
                "context_tokens_mean": ctx_tokens,
                "dropped": dropped,
            }
        )
        print(f"  [{i}/{len(sample)}] {q['id']} score={score} ctx={ctx_tokens} dropped={dropped} {time.time()-t0:.0f}s")

    summary = {
        "config": {
            "arm": "C1_full_trajectory_official_slice",
            "reader_model": Settings().deepseek_reader_model,
            "embedding_model": Settings().siliconflow_embedding_model,
            "temperature": 1.0,
            "budget_tokens": 4000,
            "top_k": 6,
            "n_questions": len(results),
            "table": args.table,
        },
        "accuracy": statistics.mean([r["mean"] for r in results]) if results else None,
        "per_question": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    json.dump(summary, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print(f"written: {out_json}  n={len(results)}  accuracy={summary['accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
