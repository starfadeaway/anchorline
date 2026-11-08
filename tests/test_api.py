# -*- coding: utf-8 -*-
"""API 冒烟测试：不依赖 MySQL（health 允许 degraded）。"""
from fastapi.testclient import TestClient

from anchorline.api.main import app


def test_health_returns_shape():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert "version" in body
    assert isinstance(body["db"], bool)


def test_chat_route_keeps_sse_shape():
    client = TestClient(app)
    r = client.post("/chat")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: error" in r.text
