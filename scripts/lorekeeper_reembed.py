# -*- coding: utf-8 -*-
"""把 LoreKeeper 的 chunk 用 Anchorline 的 Qwen3-Embedding-8B 重新嵌入，写入 Anchorline 的 LanceDB。

用途：分离「向量模型差异」与「融合策略差异」（实验 2）。
输出表：`lk_<game>_qwen8b`（在 data/lancedb）。
用法：.venv\\Scripts\\python.exe scripts\\lorekeeper_reembed.py
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import lancedb  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.llm import EmbeddingClient, ReaderConfig  # noqa: E402
from anchorline.retrieval.store import open_lancedb  # noqa: E402

LK_DIR = os.environ.get("LOREKEEPER_DIR")  # U8：必须显式设置，不再硬编码他项目本机路径
LK_LANCE = os.path.join(LK_DIR, "data", "lance")
EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"
BATCH = 8


def main() -> int:
    s = Settings()
    emb = EmbeddingClient(ReaderConfig(s.siliconflow_base_url, s.siliconflow_api_key, EMBED_MODEL))
    src = lancedb.connect(LK_LANCE)
    out = open_lancedb()
    start = time.time()
    for game in ("sr", "ys", "zzz"):
        rows = src.open_table(f"kb_{game}_baai-bge-m3_base").to_arrow().select(["id", "page_title", "text"]).to_pylist()
        vectors: list[list[float]] = []
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            vectors.extend(emb.embed([(r.get("text") or "")[:4000] for r in batch]))
            if (i // BATCH) % 50 == 0:
                print(f"  {game}: {i + len(batch)}/{len(rows)}  {time.time() - start:.0f}s", flush=True)
        data = [
            {"id": r["id"], "page_title": r.get("page_title") or "", "text": r.get("text") or "", "vector": v}
            for r, v in zip(rows, vectors)
        ]
        out.create_table(f"lk_{game}_qwen8b", data=data, mode="overwrite")
        print(f"written lk_{game}_qwen8b: {len(data)} rows", flush=True)
    print(f"done in {time.time() - start:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
