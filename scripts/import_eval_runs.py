# -*- coding: utf-8 -*-
"""把 data/eval 下的评测结果导入 MySQL `eval_runs` 表（评测结果原本只落 JSON）。

幂等：同一 (benchmark, arm, question_id, budget_tokens) 先删后插。
用法：.venv\\Scripts\\python.exe scripts/import_eval_runs.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from sqlalchemy import delete, select  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.db import session_factory  # noqa: E402
from anchorline.models import EvalRun  # noqa: E402

EVAL = os.path.join(ROOT, "data", "eval")

# (文件, arm, benchmark)
SOURCES = [
    ("b_arm_154_run3.json", "B", "v2-web"),
    ("d_arm_154_run3.json", "D", "v2-web"),
    ("c1_arm_154.json", "C1", "v2-web"),
    ("c2_arm_154.json", "C2", "v2-web"),
]


def main() -> int:
    s = Settings()
    db = session_factory()()
    inserted = 0
    try:
        for fname, arm, benchmark in SOURCES:
            path = os.path.join(EVAL, fname)
            if not os.path.exists(path):
                print("skip (missing):", fname)
                continue
            data = json.load(open(path, encoding="utf-8"))
            rows = data.get("per_question") or []
            budget = int((data.get("config") or {}).get("budget_tokens") or 4000)
            db.execute(
                delete(EvalRun).where(
                    EvalRun.benchmark == benchmark, EvalRun.arm == arm, EvalRun.budget_tokens == budget
                )
            )
            for r in rows:
                db.add(
                    EvalRun(
                        benchmark=benchmark,
                        arm=arm,
                        budget_tokens=budget,
                        question_id=str(r["question_id"]),
                        score=float(r.get("mean", 0.0)),
                        reader_model=s.deepseek_reader_model,
                        judge_model=None,
                        config_hash=None,
                    )
                )
                inserted += 1
            print(f"{fname}: {len(rows)} rows (arm={arm})")
        db.commit()
        total = len(list(db.scalars(select(EvalRun.id))))
        print(f"inserted {inserted}; eval_runs total = {total}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
