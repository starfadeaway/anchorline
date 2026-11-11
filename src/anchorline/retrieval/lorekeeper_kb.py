# -*- coding: utf-8 -*-
"""LoreKeeper 知识库桥接（可选）：聊天 agent 的 `kb_search` 工具后端。

- 索引：LoreKeeper 的 `<lorekeeper>/data/lance/kb_<game>_baai-bge-m3_base`（bge-m3 1024 维）
- 查询向量：BAAI/bge-m3（与 LoreKeeper 原生一致）
- 检索：chunk 向量 top-20 → 按 page 聚合（每页最高分）→ 页面文本 rerank → top_k
- 与 `memory_search` 分工：kb_search 查“知识库”（wiki 页面），memory_search 查“记忆”（事实）

配置：LOREKEEPER_ENABLED / LOREKEEPER_LANCE_DIR / LOREKEEPER_EMBED_MODEL。
"""
from __future__ import annotations

import logging
import os

from anchorline.config import Settings
from anchorline.llm import EmbeddingClient, ReaderConfig, rerank_client

log = logging.getLogger("anchorline.retrieval.lorekeeper")

GAMES = ("sr", "ys", "zzz")
_cache: dict[str, object] = {}


def _db(settings: Settings):
    if "db" not in _cache:
        import lancedb

        _cache["db"] = lancedb.connect(settings.lorekeeper_lance_dir)
    return _cache["db"]


def _embedder(settings: Settings) -> EmbeddingClient:
    key = f"emb:{settings.lorekeeper_embed_model}"
    if key not in _cache:
        _cache[key] = EmbeddingClient(
            ReaderConfig(settings.siliconflow_base_url, settings.siliconflow_api_key, settings.lorekeeper_embed_model)
        )
    return _cache[key]  # type: ignore[return-value]


def search(query: str, game: str | None = None, top_k: int = 3) -> list[dict]:
    """返回 [{game, page_title, text, score}]；索引/配置不可用时返回空列表（降级）。"""
    if not query.strip():
        return []
    settings = Settings()
    if not settings.lorekeeper_enabled or not os.path.isdir(settings.lorekeeper_lance_dir):
        return []
    try:
        db = _db(settings)
        vec = _embedder(settings).embed([query])[0]
    except Exception:
        log.warning("lorekeeper kb unavailable; kb_search degrades to empty", exc_info=True)
        return []

    # 表名 = kb_<game>_<embedding 模型标识>_base；由配置推导（不是写死 bge-m3）
    model = (getattr(settings, "lorekeeper_embed_model", "") or "BAAI/bge-m3").strip()
    embed_tag = model.replace("/", "-").lower()
    games = [game] if game in GAMES else list(GAMES)
    candidates: list[dict] = []
    for g in games:
        try:
            tbl = db.open_table(f"kb_{g}_{embed_tag}_base")
            rows = tbl.search(vec).select(["page_title", "text"]).limit(20).to_list()
        except Exception:
            continue
        best: dict[str, tuple[float, str]] = {}
        for r in rows:
            title = r.get("page_title") or ""
            if not title:
                continue
            dist = 1.0 - float(r.get("_distance") or 0.0)
            if title not in best or dist > best[title][0]:
                best[title] = (dist, r.get("text") or "")
        candidates.extend(
            {"game": g, "page_title": title, "text": text, "score": score}
            for title, (score, text) in best.items()
        )
    if not candidates:
        return []
    try:
        scored = rerank_client().rerank(query, [c["text"][:2000] for c in candidates], top_n=top_k)
        out: list[dict] = []
        for i, score in scored:
            if 0 <= i < len(candidates):
                c = dict(candidates[i])
                c["score"] = round(float(score), 6)  # P2-16：score 改为 rerank 分（与排序依据一致）
                out.append(c)
        return out[:top_k]
    except Exception:
        log.warning("lorekeeper rerank failed; fallback to vector score", exc_info=True)
        return sorted(candidates, key=lambda c: -c["score"])[:top_k]
