# -*- coding: utf-8 -*-
"""建 C1 臂索引：完整轨迹 + 官方切片口径（radius=1，**不去重**）+ 官方检索 top-6。

与 D（v2 / neighbor）的区别：D 用 L0 跨 state 去重；C1 保留**完整 a11y**（官方切片口径）。
用途：2×2 因子设计里的「完整轨迹 × 官方切片」格，与 B（a11y-only × 官方切片）对比 = 输入模态贡献。

输出：data/lancedb/v2_web_states_c1（与 D neighbor 同规模 1,737 行）
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
from anchorline.retrieval.baseline import (  # noqa: E402
    EMBEDDING_PRETOKEN_CHAR_CAP,
    normalize_vector,
    truncate_middle,
)
from anchorline.retrieval.store import open_lancedb  # noqa: E402

TABLE = "v2_web_states_c1"
BATCH = int(os.environ.get("ANCHORLINE_INDEX_BATCH", "16"))  # 单 state 文本较短，可批量
RADIUS = 1

STATE_TEMPLATE = "State {idx}\nURL: {url}\nAction: {action}\nThought: {thought}\nA11y lines:\n{a11y}"


def _embed(emb, texts):
    """批量 embedding；整批失败时回退逐条。"""
    try:
        return emb.embed(texts)
    except Exception as exc:
        print(f"  batch failed ({type(exc).__name__}) -> per-item", flush=True)
        out = []
        for x in texts:
            out.extend(emb.embed([x]))
        return out


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=int, default=RADIUS, help="切片半径（0=单 state；默认 1）")
    args = ap.parse_args()
    qs = load_questions()
    small = load_small()
    idx = load_traj_index()
    offsets = load_traj_offsets()
    web_trajs = web_trajectory_ids(qs, small, idx)
    print(f"web 轨迹 {len(web_trajs)} 条")

    entries = []
    for tid, rec in iter_trajectories(web_trajs, offsets):
        states = [s for s in (rec.get("states") or []) if isinstance(s, dict)]
        per_state = [
            STATE_TEMPLATE.format(
                idx=i,
                url=st.get("url") or "",
                action=st.get("action") or "<none>",
                thought=(st.get("thought") or "").strip(),
                # 不去重：完整 a11y（官方切片口径）
                a11y=(st.get("accessibility_tree") or "").strip(),
            )
            for i, st in enumerate(states)
        ]
        for i in range(len(per_state)):
            lo = max(0, i - args.radius)
            hi = min(len(per_state), i + args.radius + 1)
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
        vectors = _embed(emb, [e["text"] for e in batch])
        for e, v in zip(batch, vectors):
            rows.append({**e, "vector": normalize_vector(v)})
        if (i // BATCH) % 100 == 0:
            print(f"  {i + len(batch)}/{len(entries)}  {time.time() - t0:.0f}s", flush=True)

    open_lancedb().create_table(TABLE, data=rows, mode="overwrite")
    print(f"写入 LanceDB 表 {TABLE}：{len(rows)} 行，用时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
