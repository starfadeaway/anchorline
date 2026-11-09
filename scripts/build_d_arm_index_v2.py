# -*- coding: utf-8 -*-
"""建 D 臂 v2 索引：检索单元 = 当前 state + 相邻 state（radius=1）。

与 D 臂 v1（单 state）的区别：
  - v1：单 state 的「URL + action + thought + L0 增量」；
  - v2：center state 与其前/后各一个 state 的同类文本拼接（信息面更大，向 B 臂的
    3-state 切片靠拢，但仍保留 L0 去重与 action/thought）。

用途：检验「D 优势是否来自检索单元粒度」——若 v2 仍优于 B，则不是粒度问题。

输出：data/lancedb/v2_web_states_d_neighbor（1,737 行）
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.config import Settings  # noqa: E402
from anchorline.data.v2 import (  # noqa: E402
    iter_trajectories,
    load_questions,
    load_small,
    load_traj_index,
    load_traj_offsets,
    web_trajectory_ids,
)
from anchorline.llm import embedding_client  # noqa: E402
from anchorline.memory.l0 import L0Deduper  # noqa: E402
from anchorline.retrieval.baseline import (  # noqa: E402
    EMBEDDING_PRETOKEN_CHAR_CAP,
    normalize_vector,
    truncate_middle,
)
from anchorline.retrieval.store import open_lancedb  # noqa: E402

TABLE = "v2_web_states_d_neighbor"
BATCH = 1
RADIUS = 1

STATE_TEMPLATE = "State {idx}\nURL: {url}\nAction: {action}\nThought: {thought}\nNew a11y lines:\n{a11y}"


def main():
    qs = load_questions()
    small = load_small()
    idx = load_traj_index()
    offsets = load_traj_offsets()
    web_trajs = web_trajectory_ids(qs, small, idx)
    print(f"web 轨迹 {len(web_trajs)} 条")

    entries = []
    for tid, rec in iter_trajectories(web_trajs, offsets):
        states = [s for s in (rec.get("states") or []) if isinstance(s, dict)]
        # 先算每个 state 的 L0 增量（跨 state 去重）
        deduper = L0Deduper()
        per_state = []
        for i, st in enumerate(states):
            novel = deduper.feed(st.get("accessibility_tree") or "")
            per_state.append(STATE_TEMPLATE.format(
                idx=i,
                url=st.get("url") or "",
                action=st.get("action") or "<none>",
                thought=(st.get("thought") or "").strip(),
                a11y="\n".join(novel),
            ))
        # center state + 邻居拼接
        for i in range(len(per_state)):
            lo = max(0, i - RADIUS)
            hi = min(len(per_state), i + RADIUS + 1)
            text = "\n\n".join(per_state[lo:hi])
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

    open_lancedb().create_table(TABLE, data=rows, mode="overwrite")
    print(f"写入 LanceDB 表 {TABLE}：{len(rows)} 行，用时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
