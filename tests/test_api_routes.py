# -*- coding: utf-8 -*-
"""API 路由单测：SQLite 覆盖 get_db，索引调用打桩（不联网）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from anchorline.api.main import app
from anchorline.db import get_db
from anchorline.models import Base


@pytest.fixture()
def client(monkeypatch):
    # StaticPool：内存 SQLite 在多连接间共享同一库（否则新连接看不到表）
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # 索引调用打桩：不联网、不写 LanceDB
    from anchorline.retrieval import facts_index

    monkeypatch.setattr(facts_index, "upsert_fact", lambda *a, **k: True)
    monkeypatch.setattr(facts_index, "delete_fact", lambda *a, **k: True)

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_capacity_and_facts(client):
    assert client.get("/memory/capacity").status_code == 200
    assert client.get("/memory/facts").status_code == 200


def test_metrics_and_settings(client):
    m = client.get("/metrics").json()
    assert "p50_ms" in m and "error_rate" in m
    s = client.get("/settings").json()
    assert "reader_model" in s


def test_memory_write_search_history_patch_delete(client):
    r = client.post("/memory/write", json={"entity_id": "user:api", "attribute": "5k_pb", "value": "23:50"})
    assert r.status_code == 200
    fid = r.json()["fact_id"]

    facts = client.get("/memory/facts").json()
    assert any(f["id"] == fid for f in facts)

    assert client.post("/memory/search", json={"query": "5k", "limit": 3}).status_code == 200
    assert client.get(f"/memory/facts/{fid}/history").status_code == 200
    assert client.patch(f"/memory/facts/{fid}", json={"value": "24:00"}).status_code == 200
    assert client.delete(f"/memory/facts/{fid}").status_code == 200


def test_sessions_and_traces(client):
    sid = client.post("/sessions").json()["id"]
    assert client.get("/sessions").status_code == 200
    assert client.get(f"/sessions/{sid}/messages").json() == []
    assert client.get(f"/sessions/{sid}/traces").json() == []
    assert client.get("/traces").status_code == 200
    assert client.delete(f"/sessions/{sid}").json()["deleted"] == sid


def test_review_decision_flow(client):
    a = client.post("/memory/write", json={"entity_id": "user:rev", "attribute": "alpha_one", "value": "v1"}).json()["fact_id"]
    b = client.post("/memory/write", json={"entity_id": "user:rev", "attribute": "beta_two", "value": "v2"}).json()["fact_id"]

    r = client.post(
        "/review/decisions",
        json={"entity_id": "user:rev", "kept_fact_id": a, "invalidated_fact_ids": [b], "reason": "api-test"},
    )
    assert r.status_code == 200
    assert r.json()["kept_fact_id"] == a

    decisions = client.get("/review/decisions").json()
    assert any(d["kept_fact_id"] == a for d in decisions)
    summary = client.get("/eval/review-summary").json()
    assert summary["n"] >= 1
    assert client.get("/review/conflicts").status_code == 200


def test_eval_endpoints(client):
    assert client.get("/eval/summary").status_code == 200
    assert client.get("/eval/lorekeeper").status_code == 200
    assert client.get("/eval/review-summary").status_code == 200


def test_forget_invalidate_and_purge(client):
    client.post("/memory/write", json={"entity_id": "user:f", "attribute": "alpha_x", "value": "1"})
    assert client.post("/memory/forget", json={"entity_id": "user:f", "attribute": "alpha_x"}).status_code == 200
    b = client.post("/memory/write", json={"entity_id": "user:f", "attribute": "beta_y", "value": "2"}).json()["fact_id"]
    assert client.post(f"/memory/facts/{b}/invalidate").status_code == 200
    assert client.delete("/memory/facts").status_code == 200


def test_trace_and_404_paths(client):
    sid = client.post("/sessions").json()["id"]
    assert client.get(f"/sessions/{sid}/traces").json() == []
    assert client.get("/traces?limit=5").status_code == 200
    assert client.patch("/memory/facts/nope", json={"value": "x"}).status_code == 404
    assert client.post("/memory/forget", json={"entity_id": "user:none", "attribute": "none"}).status_code == 404


def test_chat_persists_messages(client, monkeypatch):
    from anchorline.api import main as main_mod

    monkeypatch.setattr(main_mod, "_gen_topic_bg", lambda *a, **k: None)
    monkeypatch.setattr(
        main_mod,
        "_run_agent",
        lambda *a, **k: {
            "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            "steps": 1, "stop_reason": "done", "intent": "current", "session_id": None,
            "trace_id": 1, "duration_ms": 1, "total_tokens": 2, "tool_errors": 0,
        },
    )
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert r.json()["answer"] == "hello"
    sid = r.json()["session_id"]
    msgs = client.get(f"/sessions/{sid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]

