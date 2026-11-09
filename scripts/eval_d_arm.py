# -*- coding: utf-8 -*-
"""D 臂评测：与 B 臂同一批 20 题、同一 reader/预算/判分。

支持 --n 次重复（默认 1），用于与 B 臂的 10 次均值做**同次数配对检验**。
配对检验用 sign-flip 置换检验（不依赖 scipy）。

输出：data/eval/d_arm_20.json
      docs/d_arm_pilot.md
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

import numpy as np  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.evaluation.d_arm import answer_d_arm  # noqa: E402
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import sample_deterministic  # noqa: E402
from anchorline.llm import embedding_client, reader_client  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

TABLE = "v2_web_states_d"
OUT_JSON = os.path.join(ROOT, "data", "eval", "d_arm_20.json")
OUT_MD = os.path.join(ROOT, "docs", "d_arm_pilot.md")
B_PILOT = os.path.join(ROOT, "data", "eval", "aa_pilot.json")


def sign_flip_pvalue(diffs: np.ndarray, n_perm: int = 10000, seed: int = 0) -> float:
    """配对差的 sign-flip 置换检验（双侧）：返回 p 值。

    H0：D 与 B 的配对差关于 0 对称（无差异）。
    """
    rng = np.random.default_rng(seed)
    obs = abs(float(np.mean(diffs)))
    count = 0
    for _ in range(n_perm):
        signs = rng.choice((-1.0, 1.0), size=diffs.size)
        if abs(float(np.mean(diffs * signs))) >= obs:
            count += 1
    return (count + 1) / (n_perm + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1, help="每题重复次数")
    ap.add_argument("--limit", type=int, default=20, help="题数（154 = 全部确定性题）")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None, help="结果 JSON 路径")
    ap.add_argument("--md-out", default=None, help="报告 md 路径")
    ap.add_argument("--b-ref", default=None, help="B 臂结果 JSON（默认 data/eval/aa_pilot.json）")
    args = ap.parse_args()
    out_json = args.out or OUT_JSON
    out_md = args.md_out or OUT_MD
    b_ref = args.b_ref or B_PILOT

    # 与 B 臂共用同一抽样函数，保证同题
    sample = sample_deterministic(limit=args.limit, seed=args.seed)
    tbl = open_table(TABLE)
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    results = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        scores: list[int] = []
        ctx_tokens: list[int] = []
        for _ in range(args.n):
            r = answer_d_arm(reader, embedder, tbl, q["question"], temperature=1.0)
            s = score_deterministic(r.answer, q.get("answer"), q["eval_function"])
            scores.append(1 if s else 0)
            ctx_tokens.append(r.context_tokens)
        results.append({
            "question_id": q["id"],
            "scores": scores,
            "mean": statistics.mean(scores),
            "span": max(scores) - min(scores),
            "context_tokens_mean": int(statistics.mean(ctx_tokens)),
        })
        print(f"  [{i}/{len(sample)}] {q['id']} scores={scores} {time.time()-t0:.0f}s")

    b = json.load(open(b_ref, encoding="utf-8")) if os.path.exists(b_ref) else None
    b_mean = {row["question_id"]: row["mean"] for row in (b or {}).get("per_question", [])}

    pairs = [(r["question_id"], r["mean"], b_mean[r["question_id"]])
             for r in results if r["question_id"] in b_mean]
    diffs = np.array([d - bm for _, d, bm in pairs]) if pairs else np.array([])

    summary = {
        "config": {
            "arm": "D_full_trajectory_L0_L3",
            "reader_model": Settings().deepseek_reader_model,
            "embedding_model": Settings().siliconflow_embedding_model,
            "temperature": 1.0,
            "budget_tokens": 4000,
            "top_k": 6,
            "n_questions": len(results),
            "n_per_question": args.n,
        },
        "d_accuracy": statistics.mean([r["mean"] for r in results]),
        "b_accuracy_reference": statistics.mean(b_mean.values()) if b_mean else None,
        "paired_diff_d_minus_b_mean": float(np.mean(diffs)) if diffs.size else None,
        "paired_diff_d_minus_b_median": float(np.median(diffs)) if diffs.size else None,
        "paired_permutation_pvalue": sign_flip_pvalue(diffs) if diffs.size else None,
        "per_question": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)

    lines = [
        f"# D 臂评测（{len(results)} 题）\n",
        "> 配置：D = 完整轨迹 + 我方 L0（跨 state 去重）+ 单 state 检索 top-6 + 4k 预算；reader `deepseek-flash`，temperature 1.0。",
        f"> 题集：确定性 web 题（seed={args.seed}），**D 每题 {args.n} 次**；B 参考文件 `{os.path.basename(b_ref)}`。\n",
        "| 指标 | 值 |",
        "|---|---|",
        f"| D 准确率（{args.n} 次/题均值） | **{summary['d_accuracy']:.3f}** |",
        f"| B 参考（`{os.path.basename(b_ref)}`） | **{summary['b_accuracy_reference']:.3f}** |" if b_mean else "| B 参考 | 无 |",
        f"| 配对差 D−B（均值） | **{summary['paired_diff_d_minus_b_mean']:+.3f}** |" if diffs.size else "",
        f"| 配对差中位数 | {summary['paired_diff_d_minus_b_median']:+.3f} |" if diffs.size else "",
        f"| 置换检验 p（双侧） | **{summary['paired_permutation_pvalue']:.4f}** |" if diffs.size else "",
        "",
        "## 逐题\n",
        "| qid | D 均值 | D 全距 | B(mean) |",
        "|---|---|---|---|",
    ]
    for qid, d, bm in pairs:
        row = next(r for r in results if r["question_id"] == qid)
        lines.append(f"| `{qid}` | {d:.2f} | {row['span']} | {bm:.2f} |")
    lines.extend([
        "",
        "> 判读规则（v0.8）：与 A/A 噪声底（配对 |Δ| 均值 6.3pp）比较；置换检验 p<0.05 且差异 > 噪声底才可称差异。",
        f"> B 为 10 次均值、D 为 {args.n} 次均值；若 n≠10，仍不是严格同次数，报告需注明。",
    ])
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(json.dumps({k: v for k, v in summary.items() if k != "per_question"}, ensure_ascii=False, indent=1, default=float))
    print("written:", out_json, out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
