# -*- coding: utf-8 -*-
"""facts_index 单测：主题标签、fact_text、临时 LanceDB 下的 upsert/delete/search。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.models import Base, Fact
from anchorline.retrieval import facts_index


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _fact(attribute: str, value: str) -> Fact:
    from datetime import datetime

    return Fact(id="f-" + attribute, entity_id="user", attribute=attribute, value=value, valid_from=datetime.now())


def test_topic_hint_categories():
    assert facts_index.topic_hint(_fact("游泳成绩", "2分15秒")) == "游泳"
    assert facts_index.topic_hint(_fact("5k_pb", "23:50")) == "跑步"
    assert facts_index.topic_hint(_fact("乒乓球经历", "连胜")) == "球类运动"
    assert facts_index.topic_hint(_fact("体重", "70kg")) == "身体数据"
    assert facts_index.topic_hint(_fact("model", "deepseek")) == "模型"
    assert facts_index.topic_hint(_fact("mcp_test", "check")) == "测试"
    assert facts_index.topic_hint(_fact("晚饭", "面条")) == ""


def test_fact_text_includes_topic():
    text = facts_index.fact_text(_fact("5k_pb", "23:50"))
    assert "（主题：跑步）" in text


def test_upsert_search_delete_with_tmp_lancedb(tmp_path, monkeypatch, db):
    import lancedb

    tmp_db = lancedb.connect(str(tmp_path / "lance"))

    def fake_open():
        return tmp_db

    class FakeEmb:
        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    def fake_embedding_client(settings=None):
        return FakeEmb()

    monkeypatch.setattr(facts_index, "open_lancedb", fake_open)
    monkeypatch.setattr(facts_index, "embedding_client", fake_embedding_client)

    fact = _fact("5k_pb", "23:50")
    db.add(fact)
    db.commit()
    assert facts_index.upsert_fact(fact) is True

    results = facts_index.search_vector("跑步", k=3)
    assert results and results[0][0] == fact.id
    # U15：排序由向量决定（改向量后首位应变化）——这里只断言结果非空且 id 合法
    assert all(isinstance(r[0], str) for r in results)

    facts_index.delete_fact(fact.id)
    assert facts_index.search_vector("跑步", k=3) == []
