# -*- coding: utf-8 -*-
"""重算 M3 2×2 汇总 json（数据源与 reports/m3_2x2.md 对齐）。

此前 m3_2x2.json 存的是旧值（B->C1 p=0.5011 等）且不在保护网内（评审 Z6）。
本脚本从 data/eval 的逐题结果重算 arms / contrasts，p 用精确符号翻转检验。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from eval_stats import sign_flip_exact  # noqa: E402

EVAL = os.path.join(ROOT, "data", "eval")
OUT = os.path.join(EVAL, "m3_2x2.json")

ARMS = {
    "B": ("b_arm_154_run3.json", "a11y-only", "official"),
    "C2": ("c2_arm_154.json", "a11y-only", "L0+L3"),
    "C1": ("c1_arm_154.json", "full", "official"),
    "D": ("d_arm_154_run3.json", "full", "L0+L3"),
    "D_neighbor": ("d_arm_154_neighbor.json", "full", "L0+L3"),
}

CONTRASTS = [
    ("B", "C1"),
    ("C2", "D"),
    ("B", "C2"),
    ("C1", "D"),
    ("B", "D"),
    ("C1", "D_neighbor"),
    ("D", "D_neighbor"),
]


def _means(name: str) -> dict[str, float]:
    path = os.path.join(EVAL, ARMS[name][0])
    rows = json.load(open(path, encoding="utf-8"))["per_question"]
    return {r["question_id"]: float(r["mean"]) for r in rows}


def main() -> int:
    means = {k: _means(k) for k in ARMS}
    arms = {
        k: {"input": ARMS[k][1], "compression": ARMS[k][2], "acc": round(sum(m.values()) / len(m), 4)}
        for k, m in means.items()
    }
    contrasts = []
    for a, b in CONTRASTS:
        common = sorted(set(means[a]) & set(means[b]))
        diffs = [means[b][q] - means[a][q] for q in common]
        contrasts.append(
            {
                "pair": f"{a} -> {b}",
                "n": len(common),
                "acc_a": arms[a]["acc"],
                "acc_b": arms[b]["acc"],
                "diff": round(sum(diffs) / len(diffs), 4) if diffs else 0.0,
                "p": round(sign_flip_exact([float(x) for x in diffs]), 4),
                "provenance": {"a": ARMS[a][0], "b": ARMS[b][0]},
            }
        )
    payload = {
        "_note": "由 scripts/rebuild_m3_2x2.py 从 data/eval 逐题结果重算；diff = acc_b - acc_a（A -> B 方向）；p 为精确符号翻转。",
        "arms": arms,
        "contrasts": contrasts,
    }
    json.dump(payload, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("written:", OUT)
    for c in contrasts:
        print(f"  {c['pair']:<20} n={c['n']} diff={c['diff']:+.4f} p={c['p']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
