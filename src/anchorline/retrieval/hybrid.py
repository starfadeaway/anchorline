# -*- coding: utf-8 -*-
"""混合检索：BM25Plus（jieba 分词）+ 向量（LanceDB）+ RRF 融合 + BGE rerank。

返回 facts 与可解释的召回明细（bm25 / vector / rrf / rerank 分数）。
向量索引不可用时自动回退到纯文本检索。
"""
from __future__ import annotations

import logging

import jieba
from sqlalchemy import select

from anchorline.llm import rerank_client
from anchorline.models import Fact
from anchorline.retrieval import facts_index

log = logging.getLogger("anchorline.retrieval.hybrid")


def tokenize(text: str) -> list[str]:
    return [t for t in jieba.lcut(text or "") if t.strip()]


def current_facts(db) -> list[Fact]:
    return list(db.scalars(select(Fact).where(Fact.valid_to.is_(None))))


def bm25_rank(facts: list[Fact], query: str) -> list[tuple[str, float]]:
    if not facts:
        return []
    # BM25Plus：IDF 恒正，避免小语料下 BM25Okapi 出现负分导致检索为空
    from rank_bm25 import BM25Plus

    corpus = [tokenize(facts_index.fact_text(f)) for f in facts]
    bm = BM25Plus(corpus)
    scores = bm.get_scores(tokenize(query))
    order = sorted(range(len(facts)), key=lambda i: -float(scores[i]))
    return [(facts[i].id, float(scores[i])) for i in order if scores[i] > 0]


def rrf_fuse(rank_lists: list[list[str]], k: int = 60, top: int = 20) -> list[str]:
    """Reciprocal Rank Fusion：多路召回按名次融合。"""
    scores: dict[str, float] = {}
    for ids in rank_lists:
        for rank, fid in enumerate(ids):
            scores[fid] = scores.get(fid, 0.0) + 1.0 / (k + rank + 1)
    return [fid for fid, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:top]]


def hybrid_search_with_recalls(
    db, query: str, top_k: int = 5, recall: int = 20, use_rerank: bool = True
) -> tuple[list[Fact], list[dict]]:
    """返回 (top facts, 召回明细)。明细字段：fact_id / entity / attribute / value / 各路分数。"""
    facts = current_facts(db)
    if not facts or not (query or "").strip():
        return [], []
    by_id = {f.id: f for f in facts}

    bm25 = bm25_rank(facts, query)
    vector = facts_index.search_vector(query, k=recall)
    bm25_map = dict(bm25)
    vec_map = dict(vector)

    rrf_scores: dict[str, float] = {}
    for ids in ([fid for fid, _ in bm25], [fid for fid, _ in vector]):
        for rank, fid in enumerate(ids):
            rrf_scores[fid] = rrf_scores.get(fid, 0.0) + 1.0 / (60 + rank + 1)
    fused = [fid for fid, _ in sorted(rrf_scores.items(), key=lambda kv: -kv[1])[: recall * 2]]
    candidates = [by_id[fid] for fid in fused if fid in by_id]
    if not candidates:
        return [], []

    rerank_scores: dict[str, float] = {}
    if use_rerank and len(candidates) > 1:
        try:
            scored = rerank_client().rerank(
                query, [facts_index.fact_text(f) for f in candidates], top_n=top_k
            )
            rerank_scores = {candidates[i].id: float(s) for i, s in scored if 0 <= i < len(candidates)}
            candidates = [candidates[i] for i, _ in scored if 0 <= i < len(candidates)]
        except Exception:
            log.warning("rerank failed; fallback to RRF order", exc_info=True)

    top = candidates[:top_k]
    recalls = [
        {
            "fact_id": f.id,
            "entity_id": f.entity_id,
            "attribute": f.attribute,
            "value": f.value,
            "bm25": round(bm25_map.get(f.id, 0.0), 4),
            "vector": round(vec_map.get(f.id, 0.0), 4),
            "rrf": round(rrf_scores.get(f.id, 0.0), 4),
            "rerank": round(rerank_scores[f.id], 4) if f.id in rerank_scores else None,
        }
        for f in top
    ]
    return top, recalls


def hybrid_search(db, query: str, top_k: int = 5, recall: int = 20, use_rerank: bool = True) -> list[Fact]:
    facts, _ = hybrid_search_with_recalls(db, query, top_k=top_k, recall=recall, use_rerank=use_rerank)
    return facts
