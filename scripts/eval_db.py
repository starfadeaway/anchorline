# -*- coding: utf-8 -*-
"""评测结果落库（eval_runs 表）：幂等写入，DB 不可用时静默跳过。

各评测脚本在写完 JSON 后调用：write_eval_runs(arm, rows, reader_model, benchmark, budget)。
rows 需含 question_id 与 mean。
"""
from __future__ import annotations


def write_eval_runs(
    arm: str,
    rows: list[dict],
    reader_model: str,
    benchmark: str = "v2-web",
    budget: int = 4000,
) -> int:
    try:
        from sqlalchemy import delete

        from anchorline.db import session_factory
        from anchorline.models import EvalRun

        db = session_factory()()
        try:
            db.execute(
                delete(EvalRun).where(
                    EvalRun.benchmark == benchmark,
                    EvalRun.arm == arm,
                    EvalRun.budget_tokens == budget,
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
                        reader_model=reader_model,
                    )
                )
            db.commit()
            print(f"eval_runs: wrote {len(rows)} rows (arm={arm}, benchmark={benchmark})")
            return len(rows)
        finally:
            db.close()
    except Exception as exc:  # DB 不可用（CI 无 MySQL）时不影响评测产物
        print(f"eval_runs write skipped ({type(exc).__name__}): {exc}")
        return 0
