# -*- coding: utf-8 -*-
"""M3 的 168 题汇总：154 道确定性题 + 14 道 llm_gotchas_checker（judge）。

流程：
  1. 对 14 道 gotchas 题，B 臂与 D 臂各跑一次（高 max_tokens）；
  2. 用冻结 prompt 的 judge（DeepSeek）判 0/1；
  3. 合并已有的 154 题确定性结果（b_arm_154_v2/d_arm_154_v2）；
  4. 输出 168 题两臂准确率、配对差、置换检验、judge prompt sha256。

输出：data/eval/arm_168.json
      docs/m3_168.md
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import numpy as np  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.data.v2 import load_questions  # noqa: E402
from anchorline.evaluation.baseline_arm import answer_baseline  # noqa: E402
from anchorline.evaluation.d_arm import answer_d_arm  # noqa: E402
from anchorline.evaluation.gotchas_judge import judge_gotchas, prompt_sha256  # noqa: E402
from anchorline.llm import embedding_client, judge_client, reader_client  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

OUT_JSON = os.path.join(ROOT, "data", "eval", "arm_168.json")
OUT_MD = os.path.join(ROOT, "docs", "m3_168.md")
B_154 = os.path.join(ROOT, "data", "eval", "b_arm_154_v2.json")
D_154 = os.path.join(ROOT, "data", "eval", "d_arm_154_v2.json")


def sign_flip_pvalue(diffs: np.ndarray, n_perm: int = 10000, seed: int = 0) -> float:
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
    ap.add_argument("--b-154", default=B_154)
    ap.add_argument("--d-154", default=D_154)
    args = ap.parse_args()

    qs = load_questions()
    gotchas = [
        q for q in qs.values()
        if str(q.get("environment", "")).startswith("webarena")
        and q["eval_function"].split("|")[0] == "llm_gotchas_checker"
        and not q["id"].endswith("_abs")
    ]
    print(f"gotchas 题：{len(gotchas)}")

    tbl_b = open_table("v2_web_slices")
    tbl_d = open_table("v2_web_states_d")
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())
    judge = judge_client(Settings())

    rows = []
    for i, q in enumerate(gotchas, 1):
        rb = answer_baseline(reader, embedder, tbl_b, q["question"], temperature=1.0)
        rd = answer_d_arm(reader, embedder, tbl_d, q["question"], temperature=1.0)
        jb = judge_gotchas(judge, q["question"], str(q.get("answer")), rb.answer)
        jd = judge_gotchas(judge, q["question"], str(q.get("answer")), rd.answer)
        rows.append({
            "question_id": q["id"],
            "question": q["question"],
            "gold": q.get("answer"),
            "b_answer": rb.answer,
            "d_answer": rd.answer,
            "b_label": jb["label"],
            "b_reason": jb["reason"],
            "d_label": jd["label"],
            "d_reason": jd["reason"],
        })
        print(f"  [{i}/{len(gotchas)}] {q['id']} b={jb['label']} d={jd['label']}")

    # 合并 154 + 14
    b154 = json.load(open(args.b_154, encoding="utf-8")) if os.path.exists(args.b_154) else None
    d154 = json.load(open(args.d_154, encoding="utf-8")) if os.path.exists(args.d_154) else None
    b154_rows = {r["question_id"]: r for r in (b154 or {}).get("per_question", [])}
    d154_rows = {r["question_id"]: r for r in (d154 or {}).get("per_question", [])}

    b_scores = {qid: r["mean"] for qid, r in b154_rows.items()}
    d_scores = {qid: r["mean"] for qid, r in d154_rows.items()}
    for r in rows:
        b_scores[r["question_id"]] = 1 if r["b_label"] == 1 else 0
        d_scores[r["question_id"]] = 1 if r["d_label"] == 1 else 0

    common = sorted(set(b_scores) & set(d_scores))
    diffs = np.array([d_scores[q] - b_scores[q] for q in common])
    summary = {
        "n_common": len(common),
        "n_deterministic_154": len(b154_rows),
        "n_gotchas_14": len(rows),
        "b_accuracy": statistics.mean([b_scores[q] for q in common]),
        "d_accuracy": statistics.mean([d_scores[q] for q in common]),
        "paired_diff_d_minus_b": float(np.mean(diffs)),
        "paired_permutation_pvalue": sign_flip_pvalue(diffs),
        "judge_prompt_sha256": prompt_sha256(),
        "judge_model": Settings().deepseek_judge_model,
        "gotchas_rows": rows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)

    lines = [
        "# M3 168 题汇总（154 确定性 + 14 judge）\n",
        f"- 题数：154 + {len(rows)} = {len(common)}",
        f"- B（官方基线）准确率：**{summary['b_accuracy']:.4f}**",
        f"- D（完整轨迹 + L0）准确率：**{summary['d_accuracy']:.4f}**",
        f"- 配对差 D−B：**{summary['paired_diff_d_minus_b']:+.4f}**",
        f"- 置换检验 p：**{summary['paired_permutation_pvalue']:.4f}**",
        f"- judge：`{summary['judge_model']}`，冻结 prompt sha256 `{summary['judge_prompt_sha256']}`\n",
        "## 14 道 gotchas 逐题\n",
        "| qid | B label | D label | B 答案（前 80） | D 答案（前 80） |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['question_id']}` | {r['b_label']} | {r['d_label']} | "
            f"{str(r['b_answer'])[:80].replace('|','/')} | {str(r['d_answer'])[:80].replace('|','/')} |"
        )
    lines.extend([
        "",
        "> 168 题中 14 道由 LLM judge 判分；judge prompt 已冻结并记录 sha256。",
        "> 本文档口径：不进官方 leaderboard；只报同 reader/judge/预算下的相对结果。",
    ])
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(json.dumps({k: v for k, v in summary.items() if k != "gotchas_rows"}, ensure_ascii=False, indent=1, default=float))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
