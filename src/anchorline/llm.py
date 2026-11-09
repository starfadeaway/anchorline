# -*- coding: utf-8 -*-
"""OpenAI-compatible 客户端：reader / judge（DeepSeek）与 embedding（SiliconFlow）。

纪律（v0.8）：
  - 评测模式固定 reader / embedding / judge，不改动、不按题切换；
  - key 只从 Settings（.env）读取，任何日志都不得输出 key；
  - 模型与官方默认（Qwen3.5-9B / Qwen3-Embedding-8B / gpt-5.2）不同 → 报告只报同配置相对结果。
"""
from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from anchorline.config import Settings


@dataclass
class ReaderConfig:
    base_url: str
    api_key: str
    model: str


class ChatClient:
    """reader / judge 共用同一种 OpenAI-compatible 客户端（模型可不同）。"""

    def __init__(self, cfg: ReaderConfig):
        self.cfg = cfg
        self._client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

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
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

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


class EmbeddingClient:
    def __init__(self, cfg: ReaderConfig):
        self.cfg = cfg
        self._client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.cfg.model, input=texts)
        return [item.embedding for item in resp.data]


def reader_client(settings: Settings | None = None) -> ChatClient:
    s = settings or Settings()
    return ChatClient(ReaderConfig(s.deepseek_base_url, s.deepseek_api_key, s.deepseek_reader_model))


def judge_client(settings: Settings | None = None) -> ChatClient:
    s = settings or Settings()
    return ChatClient(ReaderConfig(s.deepseek_base_url, s.deepseek_api_key, s.deepseek_judge_model))


def embedding_client(settings: Settings | None = None) -> EmbeddingClient:
    s = settings or Settings()
    return EmbeddingClient(ReaderConfig(s.siliconflow_base_url, s.siliconflow_api_key, s.siliconflow_embedding_model))


def chat_client(provider: str = "deepseek", settings: Settings | None = None) -> ChatClient:
    """聊天模式（非评测）可选 provider；评测模式固定用 reader_client/judge_client。

    provider: "deepseek"（默认）| "minimax"
    """
    s = settings or Settings()
    p = (provider or "deepseek").strip().lower()
    if p == "minimax":
        return ChatClient(ReaderConfig(s.minimax_base_url, s.minimax_api_key, s.minimax_model))
    return ChatClient(ReaderConfig(s.deepseek_base_url, s.deepseek_api_key, s.deepseek_reader_model))
