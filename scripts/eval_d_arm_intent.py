# -*- coding: utf-8 -*-
"""D 臂 + 回溯意图识别对照（V2 主集 154 题）：看意图提示能否提升 D。

与 `eval_d_arm.py` 同一抽样/表/reader/判分；唯一变量：每题先判意图，retrospective 时注入系统提示。
对比：d_arm_154_run3.json（D 无意图）。

输出：data/eval/d_arm_154_intent.json + reports/m3_d_intent.md
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
from anchorline.memory.intent import classify_intent  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

TABLE = "v2_web_states_d"
OUT_JSON = os.path.join(ROOT, "data", "eval", "d_arm_154_intent.json")
OUT_MD = os.path.join(ROOT, "reports", "m3_d_intent.md")
REF_RUN3 = os.path.join(ROOT, "data", "eval", "d_arm_154_run3.json")
RETRO_HINT = (
    "问题问的是过去/最初的值。请从记忆条目里找较早的状态回答，不要给当前状态。"
)


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
    ap.add_argument("--limit", type=int, default=154)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--ref", default=REF_RUN3)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--md-out", default=OUT_MD)
    args = ap.parse_args()

    sample = sample_deterministic(limit=args.limit, seed=args.seed)
    tbl = open_table(TABLE)
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    results = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        intent = classify_intent(q["question"], Settings().deepseek_reader_model)
        hint = RETRO_HINT if intent == "retrospective" else None
        scores = []
        for _ in range(args.n):
            r = answer_d_arm(reader, embedder, tbl, q["question"], temperature=1.0, system_hint=hint)
            scores.append(1 if score_deterministic(r.answer, q.get("answer"), q["eval_function"]) else 0)
        results.append({"question_id": q["id"], "intent": intent, "scores": scores, "mean": statistics.mean(scores)})
        print(f"  [{i}/{len(sample)}] {q['id']} intent={intent} scores={scores} {time.time()-t0:.0f}s")

    ref = json.load(open(args.ref, encoding="utf-8"))
    ref_mean = {r["question_id"]: r["mean"] for r in ref["per_question"]}
    pairs = [(r["question_id"], r["mean"], ref_mean[r["question_id"]]) for r in results if r["question_id"] in ref_mean]
    diffs = np.array([cur - old for _, cur, old in pairs])
    summary = {
        "config": {"table": TABLE, "n_questions": len(results), "n_per_question": args.n, "seed": args.seed},
        "acc_intent": statistics.mean([r["mean"] for r in results]),
        "acc_ref": statistics.mean([old for _, _, old in pairs]) if pairs else None,
        "paired_diff_mean": float(np.mean(diffs)) if diffs.size else None,
        "paired_pvalue": sign_flip_pvalue(diffs) if diffs.size else None,
        "per_question": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    retro = [r for r in results if r["intent"] == "retrospective"]
    lines = [
        "# D 臂 + 回溯意图识别（V2 154 题）\n",
        "> 唯一变量：每题先判 current/retrospective，retrospective 时注入「取较早状态」提示。",
        f"> 对照：`{os.path.basename(args.ref)}`（D 无意图）。\n",
        "| 指标 | 值 |",
        "|---|---|",
        f"| D + 意图 准确率 | **{summary['acc_intent']:.4f}** |",
        f"| D 对照 准确率 | {summary['acc_ref']:.4f} |",
        f"| 配对差 | **{summary['paired_diff_mean']:+.4f}**（p={summary['paired_pvalue']:.4f}） |",
        f"| 判为 retrospective 的题 | {len(retro)} / {len(results)} |",
        "",
        "## 逐题（意图为 retrospective）\n",
        "| qid | intent | scores |",
        "|---|---|---|",
    ]
    for r in retro:
        lines.append(f"| `{r['question_id']}` | {r['intent']} | {r['scores']} |")
    with open(args.md_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps({k: v for k, v in summary.items() if k != "per_question"}, ensure_ascii=False, indent=1))
    print("written:", args.out, args.md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
