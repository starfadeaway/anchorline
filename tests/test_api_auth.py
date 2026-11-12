# -*- coding: utf-8 -*-
"""鉴权中间件：正反路径（无 token 不拦 / 缺 token 401 / 错 token 401 / 对 token 200）。"""
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
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_auth_disabled_without_token(client, monkeypatch):
    """没设 API_TOKEN：受保护路由不拦（对照组）。"""
    monkeypatch.setenv("API_TOKEN", "")
    r = client.get("/sessions?limit=1")
    assert r.status_code == 200


def test_auth_rejects_missing_token(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-secret-token")
    r = client.get("/sessions?limit=1")
    assert r.status_code == 401


def test_auth_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-secret-token")
    r = client.get("/sessions?limit=1", headers={"X-API-Token": "wrong"})
    assert r.status_code == 401


def test_auth_accepts_correct_token(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-secret-token")
    r = client.get("/sessions?limit=1", headers={"X-API-Token": "test-secret-token"})
    assert r.status_code == 200


def test_health_is_exempt_even_with_token(client, monkeypatch):
    """豁免路径不要求 token（health 用于探活）。"""
    monkeypatch.setenv("API_TOKEN", "test-secret-token")
    r = client.get("/health")
    assert r.status_code == 200
