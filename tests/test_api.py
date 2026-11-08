# -*- coding: utf-8 -*-
"""API 冒烟测试：不依赖 MySQL / 不触发真实 LLM。"""
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


def test_chat_routes_registered():
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/chat" in paths
    assert "/chat/stream" in paths
