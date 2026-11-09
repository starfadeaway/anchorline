# -*- coding: utf-8 -*-
"""OpenAI-compatible 客户端：reader / judge（DeepSeek）与 embedding（SiliconFlow）。

纪律（v0.8）：
  - 评测模式固定 reader / embedding / judge，不改动、不按题切换；
  - key 只从 Settings（.env）读取，任何日志都不得输出 key；
  - 模型与官方默认（Qwen3.5-9B / Qwen3-Embedding-8B / gpt-5.2）不同 → 报告只报同配置相对结果。
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from anchorline.config import Settings

log = logging.getLogger("anchorline.llm")

_settings_cache: Settings | None = None


def _retry_settings() -> Settings:
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = Settings()
    return _settings_cache


@dataclass
class ReaderConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = 120.0


def _is_retryable(exc: BaseException) -> bool:
    """429/5xx/超时/连接错误可重试；4xx（除 429）不重试。"""
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 504)
    # httpx 异常（rerank 走 httpx）
    try:
        import httpx

        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in (429, 500, 502, 503, 504)
    except Exception:
        pass
    return False


def _retry(fn, *, label: str = "llm"):
    """指数退避重试（次数/间隔可配置）；不可重试错误直接抛出。"""
    s = _retry_settings()
    attempts = max(1, int(getattr(s, "llm_max_retries", 3) or 3))
    base = float(getattr(s, "llm_retry_base_delay_s", 0.5) or 0.5)
    last: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - 需要按类型判断是否重试
            last = exc
            if i == attempts - 1 or not _is_retryable(exc):
                raise
            delay = base * (2**i) + random.uniform(0, 0.3)
            log.warning(
                "retry %s (%d/%d) after %.1fs: %s", label, i + 1, attempts, delay, type(exc).__name__
            )
            time.sleep(delay)
    if last is not None:
        raise last


class ChatClient:
    """reader / judge 共用同一种 OpenAI-compatible 客户端（模型可不同）。"""

    def __init__(self, cfg: ReaderConfig):
        self.cfg = cfg
        self._client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.timeout, max_retries=0)

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        kwargs: dict = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tools is not None:
            kwargs["tools"] = tools

        def _call() -> str:
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""

        return _retry(_call, label=f"complete:{self.cfg.model}")

    def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> dict:
        """返回 {"content": str, "tool_calls": [{"id","name","arguments"}]}。

        reasoning 模型（如 deepseek-flash）会先花 token 思考，max_tokens 必须给足，
        否则 content 为空、tool_calls 为空。
        """
        def _call() -> dict:
            resp = self._client.chat.completions.create(
                model=self.cfg.model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            msg = resp.choices[0].message
            calls = []
            for tc in msg.tool_calls or []:
                calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                })
            return {"content": msg.content or "", "tool_calls": calls}

        return _retry(_call, label=f"tools:{self.cfg.model}")


class EmbeddingClient:
    def __init__(self, cfg: ReaderConfig):
        self.cfg = cfg
        self._client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.timeout, max_retries=0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        def _call() -> list[list[float]]:
            resp = self._client.embeddings.create(model=self.cfg.model, input=texts)
            return [item.embedding for item in resp.data]

        return _retry(_call, label=f"embed:{self.cfg.model}")


def reader_client(settings: Settings | None = None) -> ChatClient:
    s = settings or Settings()
    return ChatClient(ReaderConfig(s.deepseek_base_url, s.deepseek_api_key, s.deepseek_reader_model, s.llm_timeout_s))


def judge_client(settings: Settings | None = None) -> ChatClient:
    s = settings or Settings()
    return ChatClient(ReaderConfig(s.deepseek_base_url, s.deepseek_api_key, s.deepseek_judge_model, s.llm_timeout_s))


def embedding_client(settings: Settings | None = None) -> EmbeddingClient:
    s = settings or Settings()
    return EmbeddingClient(
        ReaderConfig(s.siliconflow_base_url, s.siliconflow_api_key, s.siliconflow_embedding_model, s.llm_timeout_s)
    )


class RerankClient:
    """SiliconFlow /rerank 客户端（BGE reranker）。"""

    def __init__(self, cfg: ReaderConfig):
        self.cfg = cfg

    def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[tuple[int, float]]:
        """返回 [(doc_index, relevance_score)]，按分数降序。"""
        import httpx

        url = self.cfg.base_url.rstrip("/") + "/rerank"

        def _call() -> list[tuple[int, float]]:
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self.cfg.api_key}"},
                json={"model": self.cfg.model, "query": query, "documents": documents, "top_n": top_n},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return [(int(x["index"]), float(x["relevance_score"])) for x in data.get("results", [])]

        return _retry(_call, label=f"rerank:{self.cfg.model}")


def rerank_client(settings: Settings | None = None) -> RerankClient:
    s = settings or Settings()
    return RerankClient(
        ReaderConfig(s.siliconflow_base_url, s.siliconflow_api_key, s.siliconflow_rerank_model, s.llm_timeout_s)
    )


def chat_client(provider: str = "deepseek", settings: Settings | None = None) -> ChatClient:
    """聊天模式（非评测）可选 provider；评测模式固定用 reader_client/judge_client。

    provider: "deepseek"（默认）| "minimax"
    """
    s = settings or Settings()
    p = (provider or "deepseek").strip().lower()
    if p == "minimax":
        return ChatClient(ReaderConfig(s.minimax_base_url, s.minimax_api_key, s.minimax_model, s.llm_timeout_s))
    return ChatClient(ReaderConfig(s.deepseek_base_url, s.deepseek_api_key, s.deepseek_reader_model, s.llm_timeout_s))
