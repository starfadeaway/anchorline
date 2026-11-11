# -*- coding: utf-8 -*-
"""C2 臂 154 题评测：a11y-only + 我方 L0 去重 + 4k 组装。

与 B 臂同索引、同 reader、同判分；输出独立文件，不影响 D 臂结果。
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
from anchorline.evaluation.c2_arm import answer_c2  # noqa: E402
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import sample_deterministic  # noqa: E402
from anchorline.llm import embedding_client, reader_client  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

OUT_JSON = os.path.join(ROOT, "data", "eval", "c2_arm_154.json")
OUT_MD = os.path.join(ROOT, "reports", "c2_arm_154.md")
B_REF = os.path.join(ROOT, "data", "eval", "b_arm_154_run2.json")


def sign_flip_pvalue(diffs, n_perm: int = 10000, seed: int = 0) -> float:
    """精确符号翻转 p 值（确定性；不依赖 numpy 版本）。"""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from eval_stats import sign_flip_exact

    return sign_flip_exact([float(x) for x in diffs])

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_JSON, help="结果 JSON 路径")
    ap.add_argument("--md-out", default=OUT_MD, help="Markdown 路径")
    ap.add_argument("--limit", type=int, default=154)
    ap.add_argument("--b-ref", default=B_REF)
    args = ap.parse_args()

    sample = sample_deterministic(limit=args.limit, seed=42)
    tbl = open_table("v2_web_slices")  # 与 B 臂同一索引
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    rows = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        r = answer_c2(reader, embedder, tbl, q["question"], temperature=1.0)
        s = score_deterministic(r.answer, q.get("answer"), q["eval_function"])
        rows.append({
            "question_id": q["id"],
            "scores": [1 if s else 0],
            "mean": 1.0 if s else 0.0,
            "context_tokens": r.context_tokens,
            "dropped": r.dropped_blocks,
        })
        print(f"  [{i}/{len(sample)}] {q['id']} score={1 if s else 0} ctx={r.context_tokens}t {time.time()-t0:.0f}s")

    b = json.load(open(args.b_ref, encoding="utf-8")) if os.path.exists(args.b_ref) else None
    b_mean = {r["question_id"]: r["mean"] for r in (b or {}).get("per_question", [])}
    common = sorted({r["question_id"] for r in rows} & set(b_mean))
    diffs = np.array([next(r["mean"] for r in rows if r["question_id"] == qid) - b_mean[qid] for qid in common])

    summary = {
        "n_questions": len(rows),
        "accuracy": statistics.mean([r["mean"] for r in rows]),  # N7：与其它臂字段名统一
        "c2_accuracy": statistics.mean([r["mean"] for r in rows]),
        "b_accuracy": statistics.mean([b_mean[q] for q in common]) if common else None,
        "paired_diff_c2_minus_b": float(np.mean(diffs)) if diffs.size else None,
        "paired_permutation_pvalue": sign_flip_pvalue(diffs) if diffs.size else None,
        "per_question": rows,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)

    lines = [
        f"# C2 臂评测（{len(rows)} 题）\n",
        "> C2 = a11y-only + 我方 L0 行级去重 + 4k 预算组装；与 B 同索引、同 reader、同判分。",
        f"> B 参考：`{os.path.basename(args.b_ref)}`。\n",
        "| 指标 | 值 |",
        "|---|---|",
        f"| C2 准确率 | **{summary['c2_accuracy']:.4f}** |",
        f"| B 准确率 | **{summary['b_accuracy']:.4f}** |",
        f"| 配对差 C2−B | **{summary['paired_diff_c2_minus_b']:+.4f}** |",
        f"| 置换检验 p | **{summary['paired_permutation_pvalue']:.4f}** |\n",
        "> 这是 2×2 设计里「压缩层」的单变量对照：输入模态与检索都相同。",
    ]
    with open(args.md_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(json.dumps({k: v for k, v in summary.items() if k != "per_question"}, ensure_ascii=False, indent=1, default=float))
    print("written:", args.out, args.md_out)
    from eval_db import write_eval_runs

    write_eval_runs("C2", rows, Settings().deepseek_reader_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
