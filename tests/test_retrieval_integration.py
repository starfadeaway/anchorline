# -*- coding: utf-8 -*-
"""检索集成单测（打桩，不联网）：hybrid RRF+recalls、lorekeeper_kb 成功/降级、baseline 切片。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.models import Base, Fact
from anchorline.retrieval import baseline, hybrid, lorekeeper_kb


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_facts(db):
    from datetime import datetime

    f1 = Fact(id="f1", entity_id="user", attribute="5k_pb", value="23:50", valid_from=datetime.now())
    f2 = Fact(id="f2", entity_id="user", attribute="游泳成绩", value="2分15秒", valid_from=datetime.now())
    db.add_all([f1, f2])
    db.commit()
    return f1, f2


def test_hybrid_search_with_recalls(db, monkeypatch):
    _make_facts(db)
    monkeypatch.setattr(hybrid.facts_index, "search_vector", lambda q, k=20, settings=None: [("f1", 0.9), ("f2", 0.3)])

    class FakeRerank:
        def rerank(self, query, docs, top_n=5):
            return [(0, 0.77), (1, 0.12)][:top_n]

    monkeypatch.setattr(hybrid, "rerank_client", lambda: FakeRerank())

    facts, recalls = hybrid.hybrid_search_with_recalls(db, "5k 最好成绩", top_k=2)
    assert facts and facts[0].id == "f1"
    assert recalls and recalls[0]["fact_id"] == "f1"
    assert "bm25" in recalls[0] and "vector" in recalls[0] and "rrf" in recalls[0]
    assert recalls[0]["rerank"] == pytest.approx(0.77)


def test_hybrid_search_falls_back_without_hits(db, monkeypatch):
    _make_facts(db)
    monkeypatch.setattr(hybrid.facts_index, "search_vector", lambda q, k=20, settings=None: [])
    facts, recalls = hybrid.hybrid_search_with_recalls(db, "完全无关的问题xyz", top_k=2)
    assert facts == [] and recalls == []


def test_lorekeeper_kb_success(tmp_path, monkeypatch):
    from anchorline.config import Settings

    class FakeTable:
        def search(self, vec):
            return self

        def select(self, cols):
            return self

        def limit(self, k):
            return self

        def to_list(self):
            return [
                {"id": "c1", "page_title": "太空封印站", "text": "两件套效果：攻击力+12%", "_distance": 0.2},
                {"id": "c2", "page_title": "其他", "text": "无关", "_distance": 0.5},
            ]

    class FakeDB:
        def open_table(self, name):
            return FakeTable()

    class FakeEmb:
        def embed(self, texts):
            return [[0.1, 0.2]]

    monkeypatch.setattr(lorekeeper_kb, "Settings", lambda: Settings(
        lorekeeper_enabled=True,
        lorekeeper_lance_dir=str(tmp_path),
        siliconflow_base_url="http://x",
        siliconflow_api_key="k",
        lorekeeper_embed_model="BAAI/bge-m3",
    ))
    monkeypatch.setattr(lorekeeper_kb, "_db", lambda s: FakeDB())
    monkeypatch.setattr(lorekeeper_kb, "_embedder", lambda s: FakeEmb())

    class FakeRerank:
        def rerank(self, q, docs, top_n=3):
            return [(0, 0.9)][:top_n]

    monkeypatch.setattr(lorekeeper_kb, "rerank_client", lambda: FakeRerank())
    hits = lorekeeper_kb.search("太空封印站 两件套")
    assert hits and hits[0]["page_title"] == "太空封印站"


def test_lorekeeper_kb_degrades_on_error(tmp_path, monkeypatch):
    from anchorline.config import Settings

    monkeypatch.setattr(lorekeeper_kb, "Settings", lambda: Settings(
        lorekeeper_enabled=True,
        lorekeeper_lance_dir=str(tmp_path),
        siliconflow_base_url="http://x",
        siliconflow_api_key="k",
        lorekeeper_embed_model="BAAI/bge-m3",
    ))

    def boom(*a, **k):
        raise RuntimeError("no db")

    monkeypatch.setattr(lorekeeper_kb, "_db", boom)
    assert lorekeeper_kb.search("anything") == []


def test_baseline_build_entries_and_normalize():
    states = [
        {"url": "http://a", "action": "click", "accessibility_tree": "tree A"},
        {"url": "http://b", "action": "", "text": "tree B"},
        {"url": "http://c", "action": None, "accessibility_tree": "tree C"},
    ]
    entries = baseline.build_entries({"id": "traj1", "states": states})
    assert len(entries) == 3
    assert entries[0].slice_state_indexes == (0, 1)
    assert entries[1].slice_state_indexes == (0, 1, 2)
    assert "tree A" in entries[0].axtree_text
    assert baseline.axtree_of(states[1]) == "tree B"
    assert baseline.axtree_of({}) == ""
    assert baseline._state_action(states[1]) == "<none>"

    vec = baseline.normalize_vector([3.0, 4.0])
    assert vec == pytest.approx([0.6, 0.8])
    assert baseline.normalize_vector([0.0, 0.0]) == [0.0, 0.0]
