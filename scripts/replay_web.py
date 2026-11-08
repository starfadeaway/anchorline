# -*- coding: utf-8 -*-
"""回放 V2-web 100 条轨迹，走确定性摄入 workflow（L0→L1→trace）写入 MySQL。

用法：
  .venv\\Scripts\\python.exe scripts\\replay_web.py
前置：alembic upgrade head 已跑；.env 已配置。
"""
from __future__ import annotations

import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.db import session_factory  # noqa: E402
from anchorline.graph.workflows import ingest_trajectory  # noqa: E402
from anchorline.models import Trace  # noqa: E402

V2 = os.path.join(ROOT, "dataset", "v2")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    small = load(os.path.join(V2, "lme_v2_small.json"))
    offs = load(os.path.join(V2, "traj_offsets.json"))
    idx = load(os.path.join(V2, "traj_index.json"))
    qs = {}
    with open(os.path.join(V2, "questions.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                qs[q["id"]] = q

    web_qids = [qid for qid, q in qs.items() if str(q.get("environment", "")).startswith("webarena")]
    web_trajs = sorted({t for qid in web_qids for t in small.get(qid, []) if (idx.get(t) or {}).get("domain") == "web"})
    print(f"web 题 {len(web_qids)} 道；并集轨迹 {len(web_trajs)} 条")

    db = session_factory()()
    ratios, events, done = [], 0, 0
    try:
        with open(os.path.join(V2, "trajectories.jsonl"), "rb") as fh:
            for tid in web_trajs:
                fh.seek(offs[tid])
                rec = json.loads(fh.readline().decode("utf-8"))
                out = ingest_trajectory(rec, db)
                db.commit()
                ratios.append(out["l0_ratio"])
                events += out["events"]
                done += 1
    finally:
        db.close()

    print(f"已摄入 {done} 条；L1 事件合计 {events:,}")
    print(f"L0 压缩比中位 {statistics.median(ratios):.2f}×")
    db = session_factory()()
    try:
        n = db.query(Trace).count()
        ingest = db.query(Trace).filter(Trace.query.like("ingest:%")).count()
        print(f"traces 表：{n} 行（其中 ingest {ingest} 行）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
