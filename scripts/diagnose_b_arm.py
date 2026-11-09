# -*- coding: utf-8 -*-
"""B 臂错题诊断：为什么 154 题里 B 会错？

从 `b_arm_154_v2.json` 取 B 的错题（mean=0），抽 N 道重跑 B 臂，保存：
  - answer 全文、判分、与 gold 的 token F1；
  - top-6 命中轨迹（traj_id / center / similarity / goal），判断是否「检索没命中」。

分类：
  - empty：answer 为空（token 上限/模型问题）
  - near：F1 >= 0.6 或 gold 的关键数字/短语出现（近似正确但严格判 0）
  - wrong：明显答错
  - retrieval_miss：top-1 的 goal 与题目语义无关（启发式，人工复核）

输出：data/eval/b_diag.json
      reports/b_arm_diagnosis.md
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.config import Settings  # noqa: E402
from anchorline.evaluation.baseline_arm import answer_baseline  # noqa: E402
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import load_v2_questions  # noqa: E402
from anchorline.evaluation.v1_judge import token_f1  # noqa: E402
from anchorline.llm import embedding_client, reader_client  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

B_REF = os.path.join(ROOT, "data", "eval", "b_arm_154_v2.json")
OUT_JSON = os.path.join(ROOT, "data", "eval", "b_diag.json")
OUT_MD = os.path.join(ROOT, "docs", "b_arm_diagnosis.md")


def classify(r: dict) -> str:
    if not str(r["answer"]).strip():
        return "empty"
    if r["f1"] >= 0.6:
        return "near"
    return "wrong"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    b = json.load(open(B_REF, encoding="utf-8"))
    wrong_ids = [r["question_id"] for r in b["per_question"] if r["mean"] == 0]
    random.seed(args.seed)
    sample_ids = random.sample(wrong_ids, min(args.n, len(wrong_ids)))
    qs = load_v2_questions()

    tbl = open_table("v2_web_slices")
    reader = reader_client(Settings())
    embedder = embedding_client(Settings())

    rows = []
    for qid in sample_ids:
        q = qs[qid]
        r = answer_baseline(reader, embedder, tbl, q["question"], temperature=1.0)
        s = score_deterministic(r.answer, q.get("answer"), q["eval_function"])
        f1 = token_f1(r.answer, q.get("answer"))
        row = {
            "question_id": qid,
            "question": q["question"],
            "gold": q.get("answer"),
            "answer": r.answer,
            "score": 1 if s else 0,
            "f1": round(f1, 3),
            "type": classify({"answer": r.answer, "f1": f1}),
            "top_hits": [
                {"traj_id": h["traj_id"], "center": h["center"], "goal": h.get("goal", "")[:120],
                 "sim": round(1 - float(h.get("_distance") or 0), 3)}
                for h in r.hits[:3]
            ],
        }
        rows.append(row)
        print(f"[{qid}] {row['type']} score={row['score']} f1={row['f1']} | gold={str(row['gold'])[:60]!r}")
        print(f"    ans: {str(row['answer'])[:160]!r}")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    from collections import Counter
    cnt = Counter(r["type"] for r in rows)
    lines = [
        f"# B 臂错题诊断（{len(rows)} 道，154 题中 B 的错题样本）\n",
        f"- 分类：{dict(cnt)}",
        "- `empty` = 空答案；`near` = 近似正确但严格判 0；`wrong` = 明显答错。",
        "- `retrieval_miss` 需人工看 top-1 goal 是否与题面相关，这里只列证据。\n",
        "| qid | type | f1 | gold | answer（前 60） | top-1 goal（前 50） |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        top = r["top_hits"][0] if r["top_hits"] else {}
        lines.append(
            f"| `{r['question_id']}` | {r['type']} | {r['f1']} | {str(r['gold'])[:60].replace('|','/')} | "
            f"{str(r['answer'])[:60].replace('|','/')} | {str(top.get('goal',''))[:50].replace('|','/')} |"
        )
    lines.extend([
        "",
        "> 只抽了错题样本；结论以分类计数 + 人工看表为准，不外推到 154 题全量。",
    ])
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("counts:", dict(cnt))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
