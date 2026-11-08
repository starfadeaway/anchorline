# -*- coding: utf-8 -*-
"""官方基线臂（B 臂）的检索 + 上下文 + reader 调用。

B 臂定义（v0.8 §6.5）：
  - 输入模态：a11y-only；
  - 切片：官方 raw_state_slice（radius 1，不做行级去重）；
  - 检索：官方向量检索 top-6；
  - 预算档：1 档（4k 名义；实际注入量由 top-6 切片决定，记录 token 数）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from anchorline.evaluation.reader import build_messages
from anchorline.llm import ChatClient, EmbeddingClient
from anchorline.retrieval.baseline import (
    DEFAULT_TOP_K,
    QUERY_INSTRUCTION,
    format_query_for_embedding,
    normalize_vector,
)


@dataclass
class BaselineResult:
    answer: str
    hits: list[dict]
    context_tokens: int
    question: str


def retrieve(tbl, embedder: EmbeddingClient, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    qv = normalize_vector(embedder.embed([format_query_for_embedding(query)])[0])
    rows = tbl.search(qv).limit(top_k).to_list()
    return rows


def context_from_hits(hits: list[dict], query: str) -> str:
    blocks = []
    for rank, h in enumerate(hits, start=1):
        blocks.append(f"### Raw state result {rank}\n{h['state_blocks']}\n")
    return "\n\n".join(blocks) if blocks else "(empty)"


def answer_baseline(
    reader: ChatClient,
    embedder: EmbeddingClient,
    tbl,
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    temperature: float = 1.0,
    max_tokens: int = 1024,
) -> BaselineResult:
    hits = retrieve(tbl, embedder, question, top_k=top_k)
    blocks = []
    for rank, h in enumerate(hits, start=1):
        dist = float(h.get("_distance") or 0.0)
        sim = 1.0 - dist  # 向量已 L2 归一化，l2 与 cosine 单调对应
        blocks.append(
            f"### Raw state result {rank}\n"
            f"- Source raw query: {question}\n"
            f"- Retrieval rank within query: {rank}\n"
            f"- Similarity: {sim:.4f}\n"
            f"- Trajectory: {h['traj_id']}\n"
            f"- Goal: {h.get('goal', '')}\n"
            f"- Center state index: {h['center']}\n\n"
            f"Relevant state slices\n{h['state_blocks']}\n"
        )
    context = "\n\n".join(blocks) if blocks else "(empty)"
    messages = build_messages(question, context)
    answer = reader.complete(messages, temperature=temperature, max_tokens=max_tokens)
    return BaselineResult(
        answer=answer,
        hits=hits,
        context_tokens=len(context) // 4,
        question=question,
    )
