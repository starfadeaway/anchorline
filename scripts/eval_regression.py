# -*- coding: utf-8 -*-
"""评测回归检查：读已入库的评测产物，校验完整性并汇总最新准确率。

可在 CI 里跑（只读 data/eval/*.json，不需要 MySQL / dataset / API key）。
退出码：关键产物缺失或字段异常时非 0。

用法：.venv\\Scripts\\python.exe scripts\\eval_regression.py
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(ROOT, "data", "eval")

# (名称, 文件, 准确率字段)
ARMS = [
    ("B 154 v2", "b_arm_154_run2.json", "accuracy"),
    ("B 154 v3", "b_arm_154_run3.json", "accuracy"),
    ("D 154 v2", "d_arm_154_run2.json", "d_accuracy"),
    ("D 154 v3", "d_arm_154_run3.json", "d_accuracy"),
    ("168 v2 (B/D)", "arm_168_run2.json", None),
    ("168 v3 (B/D)", "arm_168_run3.json", None),
]


def load(name: str) -> dict | None:
    path = os.path.join(EVAL, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def per_question(data: dict | None) -> list:
    if not isinstance(data, dict):
        return []
    return data.get("per_question") or []


def main() -> int:
    missing = []
    print("== 评测产物回归检查 ==")
    for label, name, field in ARMS:
        data = load(name)
        if data is None:
            missing.append(name)
            print(f"{label:16s}  MISSING  ({name})")
            continue
        rows = per_question(data)
        if field:
            val = data.get(field)
            if not isinstance(val, (int, float)):
                # B 臂产物没有顶层 accuracy，用 per_question 的 mean 求均值
                means = [r.get("mean") for r in rows if isinstance(r.get("mean"), (int, float))]
                val = sum(means) / len(means) if means else None
            if isinstance(val, (int, float)):
                print(f"{label:16s}  acc={val:.4f}  n={len(rows)}")
            else:
                print(f"{label:16s}  acc=None  n={len(rows)}")
                print(f"  ! {name} 缺少 {field} 且 per_question 无 mean")
                missing.append(name)
        else:
            print(
                f"{label:16s}  B={data.get('b_accuracy', float('nan')):.4f}  "
                f"D={data.get('d_accuracy', float('nan')):.4f}  n={data.get('n_common')}"
            )
        if rows and all("mean" not in r for r in rows):
            print(f"  ! {name} 的 per_question 缺少 mean（旧格式，跳过）")

    if missing:
        print(f"\n关键产物缺失/异常：{missing}")
        return 1
    print("\nOK：所有评测产物齐全")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
