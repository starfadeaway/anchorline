# -*- coding: utf-8 -*-
"""混合检索：分词、RRF、BM25 排序、主题标签。"""
from __future__ import annotations

from datetime import datetime

from anchorline.models import Fact
from anchorline.retrieval.facts_index import fact_text, topic_hint
from anchorline.retrieval.hybrid import bm25_rank, rrf_fuse, tokenize


def _fact(entity: str, attribute: str, value: str) -> Fact:
    return Fact(
        entity_id=entity,
        attribute=attribute,
        value=value,
        valid_from=datetime(2026, 1, 1),
        confidence=1.0,
        fact_type="semantic",
    )


def test_tokenize_chinese():
    assert "跑步" in tokenize("我的跑步最好成绩")
    assert "5k" in [t.lower() for t in tokenize("5K best time")]


def test_rrf_fuses_by_rank():
    fused = rrf_fuse([["a", "b"], ["b", "c"]], top=3)
    assert fused[0] == "b"  # 两路都出现，名次加权最高
    assert set(fused) == {"a", "b", "c"}


def test_bm25_rank_prefers_matching_fact():
    facts = [
        _fact("user", "5k_pb", "23:50"),
        _fact("user", "200米游泳最好成绩", "2分15秒"),
    ]
    ranked = bm25_rank(facts, "游泳 成绩")
    assert ranked and ranked[0][0] == facts[1].id


def test_topic_hint_and_fact_text():
    f = _fact("user", "5k_pb", "23:50")
    assert topic_hint(f) == "跑步"
    assert "跑步" in fact_text(f)
    swim = _fact("user", "200米游泳最好成绩", "2分15秒")
    assert topic_hint(swim) == "游泳"
