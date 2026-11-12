# -*- coding: utf-8 -*-
"""建官方基线臂（B）的 LanceDB 切片索引。

数据加载与连接逻辑复用 `anchorline.data.v2` / `anchorline.retrieval.store`，
本脚本只负责：切片 → 截断 → embedding → 写表。

用法：.venv\\Scripts\\python.exe scripts\\build_baseline_index.py
输出：data/lancedb/v2_web_slices（100 条 web 轨迹的 raw_state slice，radius=1）
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
    DEFAULT_SLICE_RADIUS,
    EMBEDDING_PRETOKEN_CHAR_CAP,
    build_entries,
    normalize_vector,
    truncate_middle,
)
from anchorline.retrieval.store import open_lancedb  # noqa: E402

TABLE = "v2_web_slices"
BATCH = int(os.environ.get("ANCHORLINE_INDEX_BATCH", "16"))  # 批量 embedding；失败会回退逐条


def _embed(emb, texts):
    """批量 embedding；若整批失败（如 400 参数过大），回退逐条，避免整轮重建报废。"""
    try:
        return emb.embed(texts)
    except Exception as exc:
        if len(texts) > 1:
            print(f"  batch failed ({type(exc).__name__}: {str(exc)[:80]}) -> per-item", flush=True)
            out = []
            for x in texts:
                out.extend(emb.embed([x]))
            return out
        raise

# T1/Q1：B 臂单条切片上限 = 预算 4k tokens（chars/4）÷ top-6 ≈ 2666 字符。
# 封 40k 没有意义——reader 只会读到预算内的前 16k，单条超预算仍会被截断。
SLICE_CHAR_CAP = int(os.environ.get("ANCHORLINE_INDEX_SLICE_CAP", str(4000 * 4)))
# 曾按「预算 ÷ top_k ≈ 2666」封顶做实验：B 准确率从 57.14% 降到 43.51%（p=0.0011，显著变差），
# 见 docs/b_arm_slice_cap_experiment.md。默认改为「预算字符数」= 旧有效行为，仍可 env 覆盖。


def _cap_head(text: str, cap: int) -> str:
    """保头截断（Q6：不用 truncate_middle，避免把 State 块从中间拼坏）。"""
    if len(text) <= cap:
        return text
    return text[: max(0, cap - 8)] + "\n…(截断)"


def main():
    qs = load_questions()
    small = load_small()
    idx = load_traj_index()
    offsets = load_traj_offsets()
    web_trajs = web_trajectory_ids(qs, small, idx)
    print(f"web 轨迹 {len(web_trajs)} 条")

    entries = []
    goals = {}
    for tid, rec in iter_trajectories(web_trajs, offsets):
        goals[tid] = str(rec.get("goal") or "")
        entries.extend(build_entries(rec, radius=DEFAULT_SLICE_RADIUS))
    print(f"切片 {len(entries)} 条；开始 embedding（batch={BATCH}）")

    emb = embedding_client(Settings())
    rows = []
    t0 = time.time()
    for i in range(0, len(entries), BATCH):
        batch = entries[i:i + BATCH]
        vectors = _embed(emb, [truncate_middle(e.axtree_text, EMBEDDING_PRETOKEN_CHAR_CAP) for e in batch])
        for e, v in zip(batch, vectors):
            rows.append({
                "id": e.entry_id,
                "traj_id": e.trajectory_id,
                "center": e.center_state_index,
                "goal": goals.get(e.trajectory_id, ""),
                # N2/O5：与 C1/D/D_neighbor 一致，索引文本封顶 40k（防单条切片远超 4k 预算）
                "axtree_text": _cap_head(e.axtree_text, SLICE_CHAR_CAP),
                # P1：B 臂注入用 state_blocks（不是 axtree_text），必须同样封顶
                "state_blocks": _cap_head(e.state_blocks, SLICE_CHAR_CAP),
                "vector": normalize_vector(v),
            })
        if (i // BATCH) % 10 == 0:
            print(f"  {i + len(batch)}/{len(entries)}  {time.time() - t0:.0f}s", flush=True)

    open_lancedb().create_table(TABLE, data=rows, mode="overwrite")
    print(f"写入 LanceDB 表 {TABLE}：{len(rows)} 行，用时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
