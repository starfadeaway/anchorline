# -*- coding: utf-8 -*-
"""全量数据导出：把 MySQL 各表导出为 JSONL（每表一个文件）+ 汇总 JSON。

用途：备份、迁移、离线分析。输出目录默认 data/exports/<时间戳>/。
用法：.venv\\Scripts\\python.exe scripts/export_db.py [--out data/exports/xxx]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from sqlalchemy import select  # noqa: E402

from anchorline.db import session_factory  # noqa: E402
from anchorline.models import EvalRun, Fact, Message, ReviewDecision, Trace  # noqa: E402
from anchorline.models import Session as ChatSession

TABLES = {
    "facts": Fact,
    "sessions": ChatSession,
    "messages": Message,
    "traces": Trace,
    "eval_runs": EvalRun,
    "review_decisions": ReviewDecision,
}


def row_of(obj) -> dict:
    return {c.name: (getattr(obj, c.name).isoformat() if hasattr(getattr(obj, c.name), "isoformat") else getattr(obj, c.name)) for c in obj.__table__.columns}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out_dir = args.out or os.path.join(ROOT, "data", "exports", datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    db = session_factory()()
    counts = {}
    try:
        for name, model in TABLES.items():
            rows = list(db.scalars(select(model)))
            path = os.path.join(out_dir, f"{name}.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for obj in rows:
                    f.write(json.dumps(row_of(obj), ensure_ascii=False, default=str) + "\n")
            counts[name] = len(rows)
    finally:
        db.close()

    summary = {"exported_at": datetime.now().isoformat(), "tables": counts}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
