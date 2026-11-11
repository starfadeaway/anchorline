# -*- coding: utf-8 -*-
"""M3 的 2×2 因子汇总：输入模态（a11y-only / 完整轨迹）× 压缩（官方切片 / L0+L3）。

臂：B = a11y-only × 官方切片；C2 = a11y-only × L0+L3；C1 = 完整轨迹 × 官方切片；D = 完整轨迹 × L0+L3。
四个单变量对比（全用配对检验，sign-flip）：
  B vs C1 → 输入模态（官方切片下）
  C2 vs D → 输入模态（L0+L3 下）
  B vs C2 → 压缩（a11y-only 下）
  C1 vs D → 压缩（完整轨迹下）

用法：
  .venv\\Scripts\\python.exe scripts\\eval_2x2.py --b data\\eval\\b_arm_154_run3.json --c1 data\\eval\\c1_arm_154.json --c2 data\\eval\\c2_arm_154.json --d data\\eval\\d_arm_154_run3.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import numpy as np  # noqa: E402

OUT_JSON = os.path.join(ROOT, "data", "eval", "m3_2x2.json")
OUT_MD = os.path.join(ROOT, "reports", "m3_2x2.md")


def load(path: str) -> dict[str, float]:
    data = json.load(open(path, encoding="utf-8"))
    rows = data.get("per_question") or []
    return {r["question_id"]: float(r["mean"]) for r in rows if "mean" in r}


def sign_flip_pvalue(diffs, n_perm: int = 10000, seed: int = 0) -> float:
    """精确符号翻转 p 值（确定性；不依赖 numpy 版本）。"""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from eval_stats import sign_flip_exact

    return sign_flip_exact([float(x) for x in diffs])

def compare(name_a: str, a: dict[str, float], name_b: str, b: dict[str, float]) -> dict:
    common = sorted(set(a) & set(b))
    diffs = np.array([b[q] - a[q] for q in common])
    return {
        "pair": f"{name_a} -> {name_b}",
        "n": len(common),
        "acc_a": round(float(np.mean([a[q] for q in common])), 4) if common else None,
        "acc_b": round(float(np.mean([b[q] for q in common])), 4) if common else None,
        "diff": round(float(np.mean(diffs)), 4) if common else None,
        "p": round(sign_flip_pvalue(diffs), 4) if common else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b", default=os.path.join(ROOT, "data", "eval", "b_arm_154_run3.json"))
    ap.add_argument("--c1", default=os.path.join(ROOT, "data", "eval", "c1_arm_154.json"))
    ap.add_argument("--c2", default=os.path.join(ROOT, "data", "eval", "c2_arm_154.json"))
    ap.add_argument("--d", default=os.path.join(ROOT, "data", "eval", "d_arm_154_run3.json"))
    args = ap.parse_args()

    for name, path in (("B", args.b), ("C1", args.c1), ("C2", args.c2), ("D", args.d)):
        if not os.path.exists(path):
            print(f"{name} 结果缺失：{path}（先跑对应评测）")
            return 1

    b, c1, c2, d = load(args.b), load(args.c1), load(args.c2), load(args.d)
    pairs = [
        compare("B", b, "C1", c1),
        compare("C2", c2, "D", d),
        compare("B", b, "C2", c2),
        compare("C1", c1, "D", d),
    ]
    summary = {
        "arms": {
            "B": {"input": "a11y-only", "compression": "official", "acc": round(float(np.mean(list(b.values()))), 4)},
            "C2": {"input": "a11y-only", "compression": "L0+L3", "acc": round(float(np.mean(list(c2.values()))), 4)},
            "C1": {"input": "full", "compression": "official", "acc": round(float(np.mean(list(c1.values()))), 4)},
            "D": {"input": "full", "compression": "L0+L3", "acc": round(float(np.mean(list(d.values()))), 4)},
        },
        "contrasts": pairs,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    lines = [
        "# M3 2×2 因子汇总（154 题）\n",
        "> B = a11y-only × 官方切片；C2 = a11y-only × L0+L3；C1 = 完整轨迹 × 官方切片；D = 完整轨迹 × L0+L3。",
        "> reader deepseek-flash、embedding Qwen3-Embedding-8B、4k 预算、top-6；配对检验为 sign-flip。\n",
        "| 臂 | 输入 | 压缩 | 准确率 |",
        "|---|---|---|---|",
    ]
    for arm, info in summary["arms"].items():
        lines.append(f"| {arm} | {info['input']} | {info['compression']} | {info['acc']:.4f} |")
    lines += ["", "| 对比 | 方向 | n | 差 | p |", "|---|---|---|---|---|"]
    for p in pairs:
        lines.append(f"| {p['pair']} | {p['acc_a']:.4f} → {p['acc_b']:.4f} | {p['n']} | {p['diff']:+.4f} | {p['p']:.4f} |")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
