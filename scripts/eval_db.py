# -*- coding: utf-8 -*-
"""评测结果落库（eval_runs 表）：逐题 upsert（不删整臂），DB 不可用时静默跳过。

各评测脚本在写完 JSON 后调用：write_eval_runs(arm, rows, reader_model, benchmark, budget)。
rows 需含 question_id 与 mean。小样本评测只替换本次涉及的题，不会清掉该臂其它题。
"""
from __future__ import annotations


def write_eval_runs(
    arm: str,
    rows: list[dict],
    reader_model: str,
    benchmark: str = "v2-web",
    budget: int = 4000,
) -> int:
    if not rows:
        return 0
    try:
        from sqlalchemy import delete

        from anchorline.db import session_factory
        from anchorline.models import EvalRun

        db = session_factory()()
        try:
            qids = [str(r["question_id"]) for r in rows]
            # 只删本次要写的题（逐题 upsert），保留该臂其它题的结果
            db.execute(
                delete(EvalRun).where(
                    EvalRun.benchmark == benchmark,
                    EvalRun.arm == arm,
                    EvalRun.budget_tokens == budget,
                    EvalRun.question_id.in_(qids),
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
            print(f"eval_runs: upserted {len(rows)} rows (arm={arm}, benchmark={benchmark})")
            return len(rows)
        finally:
            db.close()
    except Exception as exc:  # DB 不可用（CI 无 MySQL）时不影响评测产物
        print(f"eval_runs write skipped ({type(exc).__name__}): {exc}")
        return 0
