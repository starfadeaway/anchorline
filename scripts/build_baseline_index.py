# -*- coding: utf-8 -*-
"""建官方基线臂（B）的 LanceDB 切片索引。

用法：.venv\\Scripts\\python.exe scripts\\build_baseline_index.py
输出：data/lancedb/v2_web_slices（100 条 web 轨迹的 raw_state slice，radius=1）
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import lancedb  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.llm import embedding_client  # noqa: E402
from anchorline.retrieval.baseline import (  # noqa: E402
    DEFAULT_SLICE_RADIUS,
    EMBEDDING_PRETOKEN_CHAR_CAP,
    build_entries,
    normalize_vector,
    truncate_middle,
)

V2 = os.path.join(ROOT, "dataset", "v2")
TABLE = "v2_web_slices"
BATCH = 1  # 单条最长 40k 字符；多条合计会触发 400 invalid parameter


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
    print(f"web 轨迹 {len(web_trajs)} 条")

    entries = []
    goals = {}
    with open(os.path.join(V2, "trajectories.jsonl"), "rb") as fh:
        for tid in web_trajs:
            fh.seek(offs[tid])
            rec = json.loads(fh.readline().decode("utf-8"))
            goals[tid] = str(rec.get("goal") or "")
            entries.extend(build_entries(rec, radius=DEFAULT_SLICE_RADIUS))
    print(f"切片 {len(entries)} 条；开始 embedding（batch={BATCH}）")

    emb = embedding_client(Settings())
    rows = []
    t0 = time.time()
    for i in range(0, len(entries), BATCH):
        batch = entries[i:i + BATCH]
        vectors = emb.embed([truncate_middle(e.axtree_text, EMBEDDING_PRETOKEN_CHAR_CAP) for e in batch])
        for e, v in zip(batch, vectors):
            rows.append({
                "id": e.entry_id,
                "traj_id": e.trajectory_id,
                "center": e.center_state_index,
                "goal": goals.get(e.trajectory_id, ""),
                "axtree_text": e.axtree_text,
                "state_blocks": e.state_blocks,
                "vector": normalize_vector(v),
            })
        if (i // BATCH) % 20 == 0:
            print(f"  {i + len(batch)}/{len(entries)}  {time.time() - t0:.0f}s")

    db = lancedb.connect(os.path.join(ROOT, "data", "lancedb"))
    db.create_table(TABLE, data=rows, mode="overwrite")
    print(f"写入 LanceDB 表 {TABLE}：{len(rows)} 行，用时 {time.time() - t0:.0f}s")
    dim = len(rows[0]["vector"]) if rows else 0
    print(f"向量维度 {dim}")


if __name__ == "__main__":
    main()
