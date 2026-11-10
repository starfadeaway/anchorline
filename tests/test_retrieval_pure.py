# -*- coding: utf-8 -*-
"""检索纯函数单测：baseline 截断/查询前缀、hybrid 分词/BM25/RRF。"""
from __future__ import annotations

from anchorline.retrieval import hybrid
from anchorline.retrieval.baseline import (
    EMBEDDING_PRETOKEN_CHAR_CAP,
    QUERY_INSTRUCTION,
    format_query_for_embedding,
    truncate_middle,
)


def test_truncate_middle_short_text_unchanged():
    assert truncate_middle("hello", 100) == "hello"


def test_truncate_middle_keeps_head_and_tail():
    text = "A" * 1000 + "B" * 1000
    out = truncate_middle(text, 200)
    assert len(out) <= 200
    assert "truncated" in out
    assert out.startswith("A")
    assert out.endswith("B")


def test_truncate_middle_small_cap_plain_slice():
    assert truncate_middle("x" * 100, 10) == "x" * 10


def test_format_query_for_embedding():
    out = format_query_for_embedding("  我的 5K 成绩  ")
    assert out.startswith(f"Instruct: {QUERY_INSTRUCTION}")
    assert "我的 5K 成绩" in out
    assert EMBEDDING_PRETOKEN_CHAR_CAP > 0


def test_hybrid_tokenize_chinese():
    tokens = hybrid.tokenize("我的 5K 最好成绩是 23:50")
    assert "5K" in tokens
    assert "23" in tokens


def test_bm25_rank_orders_by_score():
    from anchorline.models import Fact

    facts = [
        Fact(id="f1", entity_id="user", attribute="5k_pb", value="23:50"),
        Fact(id="f2", entity_id="user", attribute="游泳成绩", value="2分15秒"),
        Fact(id="f3", entity_id="user", attribute="晚饭", value="面条"),
    ]
    ranked = hybrid.bm25_rank(facts, "5k 最好成绩")
    assert ranked
    assert ranked[0][0] == "f1"
    assert all(isinstance(score, float) for _, score in ranked)


def test_rrf_fuse_prefers_items_in_multiple_lists():
    fused = hybrid.rrf_fuse([["a", "b", "c"], ["b", "a", "d"]], k=60, top=4)
    assert set(fused[:2]) == {"a", "b"}
    assert fused.index("a") < fused.index("c")
