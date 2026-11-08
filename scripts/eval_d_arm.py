# -*- coding: utf-8 -*-
"""D 臂 pilot：与 A/A 同一批 20 题，跑 1 次/题，与 B 臂（10 次均值）对比。

输出：data/eval/d_arm_20.json
      docs/d_arm_pilot.md
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import lancedb  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.evaluation.d_arm import answer_d_arm  # noqa: E402
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import sample_deterministic  # noqa: E402
from anchorline.llm import embedding_client, reader_client  # noqa: E402

V2 = os.path.join(ROOT, "dataset", "v2")
TABLE = "v2_web_states_d"
OUT_JSON = os.path.join(ROOT, "data", "eval", "d_arm_20.json")
OUT_MD = os.path.join(ROOT, "docs", "d_arm_pilot.md")
B_PILOT = os.path.join(ROOT, "data", "eval", "aa_pilot.json")


def main() -> int:
    # 与 B 臂共用同一抽样函数（seed=42），保证同题
    sample = sample_deterministic(limit=20, seed=42)

    tbl = lancedb.connect(os.path.join(ROOT, "data", "lancedb")).open_table(TABLE)
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    results = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        r = answer_d_arm(reader, embedder, tbl, q["question"], temperature=1.0)
        s = score_deterministic(r.answer, q.get("answer"), q["eval_function"])
        results.append({
            "question_id": q["id"],
            "score": 1 if s else 0,
            "context_tokens": r.context_tokens,
            "dropped": r.dropped_entries,
        })
        print(f"  [{i}/20] {q['id']} score={1 if s else 0} ctx={r.context_tokens}t {time.time()-t0:.0f}s")

    b = json.load(open(B_PILOT, encoding="utf-8")) if os.path.exists(B_PILOT) else None
    b_mean = {}
    if b:
        for row in b.get("per_question", []):
            b_mean[row["question_id"]] = row["mean"]

    d_scores = [r["score"] for r in results]
    pairs = [(r["question_id"], r["score"], b_mean.get(r["question_id"])) for r in results if b_mean]
    diffs = [d - b for _, d, b in pairs if b is not None]

    summary = {
        "config": {
            "arm": "D_full_trajectory_L0_L3",
            "reader_model": Settings().deepseek_reader_model,
            "embedding_model": Settings().siliconflow_embedding_model,
            "temperature": 1.0,
            "budget_tokens": 4000,
            "top_k": 6,
            "n_questions": len(results),
        },
        "d_accuracy": statistics.mean(d_scores),
        "b_accuracy_reference": statistics.mean(b_mean.values()) if b_mean else None,
        "paired_diff_d_minus_b_mean": statistics.mean(diffs) if diffs else None,
        "per_question": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    lines = [
        "# D 臂 pilot（20 题）\n",
        "> 配置：D = 完整轨迹 + 我方 L0（跨 state 去重）+ 事件/页面文本检索 top-6 + 4k 预算；reader `deepseek-flash`，temperature 1.0。",
        f"> 题集：与 A/A pilot 相同的 20 题（seed=42，确定性判分）。\n",
        "| 指标 | 值 |",
        "|---|---|",
        f"| D 臂准确率（1 次/题） | **{statistics.mean(d_scores):.3f}** |",
        f"| B 臂参考（A/A 10 次均值） | **{statistics.mean(b_mean.values()):.3f}** |" if b_mean else "| B 臂参考 | 无（缺 aa_pilot.json） |",
        f"| 配对差 D−B | **{(statistics.mean(diffs) if diffs else float('nan')):+.3f}** |" if diffs else "",
        "",
        "## 逐题\n",
        "| qid | D | B(mean) |",
        "|---|---|---|",
    ]
    for qid, d, bm in pairs:
        lines.append(f"| `{qid}` | {d} | {bm} |")
    lines.extend([
        "",
        "> ⚠️ 这是 20 题 pilot，单题翻转 = 5pp；差异需配对检验，不能只看均值。",
        "> B 臂为 10 次均值、D 臂为 1 次；这不是同次数对比，正式 M3 需统一 N。",
    ])
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(json.dumps({k: v for k, v in summary.items() if k != "per_question"}, ensure_ascii=False, indent=1))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
