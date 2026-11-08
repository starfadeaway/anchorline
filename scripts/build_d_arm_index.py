# -*- coding: utf-8 -*-
"""建 D 臂（本项目完整链路）的 state 级索引。

与 B 臂（官方 raw_state_slice）的区别：
  - B：相邻 3 个 state 的 a11y 原文，**不做行级去重**，检索面只 a11y；
  - D：**单 state** 为检索单元，文本 = URL + action + thought + **L0 跨 state 去重后的新增 a11y 行**，
    即「完整轨迹 + 我方 L0 压缩」。

输出：data/lancedb/v2_web_states_d（~1000 行，4096 维）
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
from anchorline.memory.l0 import L0Deduper  # noqa: E402
from anchorline.retrieval.baseline import (  # noqa: E402
    EMBEDDING_PRETOKEN_CHAR_CAP,
    normalize_vector,
    truncate_middle,
)

V2 = os.path.join(ROOT, "dataset", "v2")
TABLE = "v2_web_states_d"
BATCH = 1

ENTRY_TEMPLATE = "URL: {url}\nAction: {action}\nThought: {thought}\nNew a11y lines:\n{a11y}"


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
    with open(os.path.join(V2, "trajectories.jsonl"), "rb") as fh:
        for tid in web_trajs:
            fh.seek(offs[tid])
            rec = json.loads(fh.readline().decode("utf-8"))
            states = [s for s in (rec.get("states") or []) if isinstance(s, dict)]
            d = L0Deduper()
            for i, st in enumerate(states):
                novel = d.feed(st.get("accessibility_tree") or "")
                text = ENTRY_TEMPLATE.format(
                    url=st.get("url") or "",
                    action=st.get("action") or "<none>",
                    thought=(st.get("thought") or "").strip(),
                    a11y="\n".join(novel),
                )
                entries.append({
                    "id": f"{tid}:state:{i:04d}",
                    "traj_id": tid,
                    "state_index": i,
                    "goal": str(rec.get("goal") or ""),
                    "text": truncate_middle(text, EMBEDDING_PRETOKEN_CHAR_CAP),
                })
    print(f"state 条目 {len(entries)} 条；开始 embedding")

    emb = embedding_client(Settings())
    rows = []
    t0 = time.time()
    for i in range(0, len(entries), BATCH):
        batch = entries[i:i + BATCH]
        vectors = emb.embed([e["text"] for e in batch])
        for e, v in zip(batch, vectors):
            rows.append({**e, "vector": normalize_vector(v)})
        if (i // BATCH) % 100 == 0:
            print(f"  {i + len(batch)}/{len(entries)}  {time.time() - t0:.0f}s")

    db = lancedb.connect(os.path.join(ROOT, "data", "lancedb"))
    db.create_table(TABLE, data=rows, mode="overwrite")
    print(f"写入 LanceDB 表 {TABLE}：{len(rows)} 行，用时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
