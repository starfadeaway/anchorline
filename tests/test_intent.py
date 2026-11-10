# -*- coding: utf-8 -*-
"""意图识别产品化单测：分类器 + memory_search include_history。"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.memory import intent
from anchorline.memory.store import FactStore
from anchorline.models import Base
from anchorline.tools import build_tools


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_classify_intent_retrospective(monkeypatch):
    class FakeClient:
        def complete(self, messages, **kwargs):
            return '{"query_form": "retrospective"}'

    monkeypatch.setattr("anchorline.llm.chat_client", lambda model="deepseek": FakeClient())
    assert intent.classify_intent("我最初的 5K 成绩是多少？") == "retrospective"


def test_classify_intent_current(monkeypatch):
    class FakeClient:
        def complete(self, messages, **kwargs):
            return '{"query_form": "current"}'

    monkeypatch.setattr("anchorline.llm.chat_client", lambda model="deepseek": FakeClient())
    assert intent.classify_intent("我的 5K 成绩是多少？") == "current"


def test_classify_intent_falls_back_on_error(monkeypatch):
    class BoomClient:
        def complete(self, messages, **kwargs):
            raise RuntimeError("api down")

    monkeypatch.setattr("anchorline.llm.chat_client", lambda model="deepseek": BoomClient())
    assert intent.classify_intent("随便问") == "current"


def test_memory_search_include_history_returns_invalidated(db, monkeypatch):
    store = FactStore(db)
    old = store.write(entity_id="user", attribute="5k_pb", value="27:12", valid_from=datetime(2023, 1, 1))
    new = store.write(entity_id="user", attribute="5k_pb", value="23:50", valid_from=datetime(2023, 6, 1))
    db.commit()
    assert old.valid_to is not None

    # 混合检索返回当前值；include_history=true 时应额外带出失效的旧值
    monkeypatch.setattr("anchorline.retrieval.hybrid.hybrid_search_with_recalls", lambda *a, **k: ([new], []))
    tools = build_tools(store)
    res = tools["memory_search"](query="5k", include_history=True)
    assert "27:12" in res.content
    assert "23:50" in res.content
    assert res.meta["hits"] >= 2
    res2 = tools["memory_search"](query="5k", include_history=False)
    assert "27:12" not in res2.content
