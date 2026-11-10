# -*- coding: utf-8 -*-
"""kb_search 工具：LoreKeeper 知识库桥接（降级与文本组装）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline import tools as tools_mod
from anchorline.memory.store import FactStore
from anchorline.models import Base
from anchorline.retrieval import lorekeeper_kb


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_kb_search_disabled_returns_empty(monkeypatch):
    monkeypatch.setenv("LOREKEEPER_ENABLED", "false")
    assert lorekeeper_kb.search("太空封印站") == []


def test_kb_search_tool_formats_hits(monkeypatch, db):
    hits = [
        {"game": "sr", "page_title": "太空封印站", "text": "两件套效果：攻击力+12%", "score": 0.9},
        {"game": "sr", "page_title": "寰宇生研院", "text": "两件套效果：能量上限", "score": 0.2},
    ]
    monkeypatch.setattr(lorekeeper_kb, "search", lambda q, game=None, top_k=3: hits)
    tools = tools_mod.build_tools(FactStore(db))
    result = tools["kb_search"]("太空封印站 二件套", game="sr", top_k=2)
    assert result.ok
    assert "太空封印站" in result.content
    assert "两件套效果" in result.content
    assert result.meta["hits"] == 2
    assert result.meta["pages"] == ["太空封印站", "寰宇生研院"]


def test_kb_search_tool_empty(monkeypatch, db):
    monkeypatch.setattr(lorekeeper_kb, "search", lambda q, game=None, top_k=3: [])
    tools = tools_mod.build_tools(FactStore(db))
    result = tools["kb_search"]("不存在的问题")
    assert result.ok
    assert result.meta["hits"] == 0
