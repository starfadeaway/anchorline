# -*- coding: utf-8 -*-
"""LLM 可靠性：重试判定与指数退避。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from openai import APIStatusError

from anchorline import llm


def _err(status: int) -> APIStatusError:
    resp = MagicMock()
    resp.status_code = status
    resp.request = MagicMock()
    return APIStatusError("e", response=resp, body=None)


def test_is_retryable():
    assert llm._is_retryable(_err(429))
    assert llm._is_retryable(_err(503))
    assert not llm._is_retryable(_err(400))
    assert not llm._is_retryable(ValueError("x"))


def test_retry_eventually_succeeds(monkeypatch):
    monkeypatch.setenv("LLM_RETRY_BASE_DELAY_S", "0.01")
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    monkeypatch.setattr(llm, "_settings_cache", None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _err(429)
        return "ok"

    assert llm._retry(fn, label="t") == "ok"
    assert calls["n"] == 3


def test_retry_gives_up_after_attempts(monkeypatch):
    monkeypatch.setenv("LLM_RETRY_BASE_DELAY_S", "0.01")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setattr(llm, "_settings_cache", None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _err(503)

    with pytest.raises(APIStatusError):
        llm._retry(fn, label="t")
    assert calls["n"] == 2


def test_no_retry_for_plain_error(monkeypatch):
    monkeypatch.setattr(llm, "_settings_cache", None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("bad")

    with pytest.raises(ValueError):
        llm._retry(fn, label="t")
    assert calls["n"] == 1
