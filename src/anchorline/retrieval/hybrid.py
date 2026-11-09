# -*- coding: utf-8 -*-
"""混合检索：BM25（jieba 分词）+ 向量（LanceDB）+ RRF 融合 + BGE rerank。

聊天里的 `memory_search` 走这里；向量索引不可用时自动回退到纯文本检索。
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


def hybrid_search(db, query: str, top_k: int = 5, recall: int = 20, use_rerank: bool = True) -> list[Fact]:
    facts = current_facts(db)
    if not facts or not (query or "").strip():
        return []
    by_id = {f.id: f for f in facts}

    bm25 = bm25_rank(facts, query)
    vector = facts_index.search_vector(query, k=recall)
    fused = rrf_fuse([[fid for fid, _ in bm25], [fid for fid, _ in vector]], top=recall * 2)
    candidates = [by_id[fid] for fid in fused if fid in by_id]
    if not candidates:
        return []

    if use_rerank and len(candidates) > 1:
        try:
            scored = rerank_client().rerank(query, [facts_index.fact_text(f) for f in candidates], top_n=top_k)
            candidates = [candidates[i] for i, _ in scored if 0 <= i < len(candidates)]
        except Exception:
            log.warning("rerank failed; fallback to RRF order", exc_info=True)
    return candidates[:top_k]
