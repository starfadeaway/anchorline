# -*- coding: utf-8 -*-
"""评测回归 / 稳定性对比：同一臂两次运行的单题翻转率与汇总。

用法：
  .venv\\Scripts\\python.exe scripts\\eval_suite.py --arm b --a data\\eval\\b_arm_154_run2.json --b data\\eval\\b_arm_154_run3.json
  .venv\\Scripts\\python.exe scripts\\eval_suite.py --arm d --a data\\eval\\d_arm_154_run2.json --b data\\eval\\d_arm_154_run3.json
"""
from __future__ import annotations

import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path: str) -> dict[str, list[float]]:
    """返回 qid -> scores（取每题的分数列表）。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items") or data.get("results") or data.get("rows") or data.get("per_question") or []
    out: dict[str, list[float]] = {}
    for it in items:
        qid = it.get("question_id") or it.get("case_id") or it.get("qid")
        scores = it.get("scores") or it.get("score")
        if qid is None:
            continue
        if isinstance(scores, (int, float)):
            scores = [scores]
        if isinstance(scores, list) and scores and isinstance(scores[0], (int, float)):
            out[str(qid)] = [float(x) for x in scores]
    return out


def mean_score(scores: list[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--a", required=True, help="第一次运行结果 json")
    ap.add_argument("--b", required=True, help="第二次运行结果 json")
    args = ap.parse_args()

    a = load(args.a)
    b = load(args.b)
    common = sorted(set(a) & set(b))
    if not common:
        print("no common questions (check file format)")
        return 1

    flips = []
    for qid in common:
        sa = mean_score(a[qid])
        sb = mean_score(b[qid])
        if sa != sb:
            flips.append((qid, sa, sb))
    acc_a = sum(mean_score(a[q]) for q in common) / len(common)
    acc_b = sum(mean_score(b[q]) for q in common) / len(common)
    print(f"arm={args.arm} common={len(common)}")
    print(f"acc: run1={acc_a:.4f} run2={acc_b:.4f} diff={acc_b - acc_a:+.4f}")
    print(f"flips: {len(flips)} ({len(flips) / len(common):.1%})")
    if flips:
        print("flipped questions:")
        for qid, sa, sb in flips[:20]:
            print(f"  {qid}: {sa:.2f} -> {sb:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
