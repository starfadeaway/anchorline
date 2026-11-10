# -*- coding: utf-8 -*-
"""把 data/eval 下的评测结果导入 MySQL `eval_runs` 表（评测结果原本只落 JSON）。

包含：四臂 154 题（B/D/C1/C2）+ 168 口径的 gotchas 14 题（judge）。
幂等：逐题 upsert（复用 eval_db.write_eval_runs）。
用法：.venv\\Scripts\\python.exe scripts/import_eval_runs.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from eval_db import write_eval_runs  # noqa: E402

from anchorline.config import Settings  # noqa: E402

EVAL = os.path.join(ROOT, "data", "eval")

SOURCES = [
    ("b_arm_154_run3.json", "B", "v2-web"),
    ("d_arm_154_run3.json", "D", "v2-web"),
    ("c1_arm_154.json", "C1", "v2-web"),
    ("c2_arm_154.json", "C2", "v2-web"),
]


def main() -> int:
    s = Settings()
    total = 0
    for fname, arm, benchmark in SOURCES:
        path = os.path.join(EVAL, fname)
        if not os.path.exists(path):
            print("skip (missing):", fname)
            continue
        data = json.load(open(path, encoding="utf-8"))
        rows = data.get("per_question") or []
        budget = int((data.get("config") or {}).get("budget_tokens") or 4000)
        total += write_eval_runs(arm, rows, s.deepseek_reader_model, benchmark=benchmark, budget=budget)

    # 168 口径：gotchas 14 题（judge），按臂拆成逐题行
    p168 = os.path.join(EVAL, "arm_168_run3.json")
    if os.path.exists(p168):
        d = json.load(open(p168, encoding="utf-8"))
        gotchas = d.get("gotchas_rows") or []
        b_rows = [{"question_id": g["question_id"], "mean": float(g.get("b_label") or 0)} for g in gotchas]
        d_rows = [{"question_id": g["question_id"], "mean": float(g.get("d_label") or 0)} for g in gotchas]
        kw = {
            "benchmark": "v2-web-168",
            "budget": 4000,
            "judge_model": d.get("judge_model") or s.deepseek_judge_model,
            "judge_prompt_sha256": d.get("judge_prompt_sha256"),
        }
        total += write_eval_runs("B", b_rows, s.deepseek_reader_model, **kw)
        total += write_eval_runs("D", d_rows, s.deepseek_reader_model, **kw)
    print(f"imported {total} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
