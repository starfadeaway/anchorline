# -*- coding: utf-8 -*-
"""D 臂（本项目完整链路）：完整轨迹 + 我方 L0→L3 + 4k 预算组装。

与 B 臂同 reader / 同预算 / 同判分，便于单变量对比：
  - B：官方 raw_state_slice（3 state a11y 原文，不去重）+ 官方向量检索 top-6；
  - D：单 state 为检索单元，文本 = URL + action + thought + L0 跨 state 去重后的新增 a11y 行。
"""
from __future__ import annotations

from dataclasses import dataclass

from anchorline.evaluation.reader import build_messages
from anchorline.llm import ChatClient, EmbeddingClient
from anchorline.memory.l3 import assemble_blocks
from anchorline.retrieval.baseline import (
    DEFAULT_TOP_K,
    format_query_for_embedding,
    normalize_vector,
)


@dataclass
class DArmResult:
    answer: str
    hits: list[dict]
    context_tokens: int
    question: str
    dropped_entries: int = 0


def retrieve_d(tbl, embedder: EmbeddingClient, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    qv = normalize_vector(embedder.embed([format_query_for_embedding(query)])[0])
    return tbl.search(qv).limit(top_k).to_list()


def answer_d_arm(
    reader: ChatClient,
    embedder: EmbeddingClient,
    tbl,
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    temperature: float = 1.0,
    max_tokens: int = 4096,
    context_budget_tokens: int = 4000,
) -> DArmResult:
    hits = retrieve_d(tbl, embedder, question, top_k=top_k)
    items: list[tuple[float, str]] = []
    for h in hits:
        sim = 1.0 - float(h.get("_distance") or 0.0)
        block = (
            f"### Memory entry\n"
            f"- Trajectory: {h['traj_id']}\n"
            f"- Goal: {h.get('goal', '')}\n"
            f"- State index: {h['state_index']}\n"
            f"- Similarity: {sim:.4f}\n\n"
            f"{h['text']}\n"
        )
        items.append((sim, block))

    context, used_tokens, dropped = assemble_blocks(items, context_budget_tokens)
    context = context or "(empty)"
    messages = build_messages(question, context)
    answer = reader.complete(messages, temperature=temperature, max_tokens=max_tokens)
    if not answer.strip():
        # 同 B 臂：reasoning 模型空答案时放大上限重试一次
        answer = reader.complete(messages, temperature=temperature, max_tokens=max_tokens * 2)
    return DArmResult(
        answer=answer,
        hits=hits,
        context_tokens=used_tokens,
        question=question,
        dropped_entries=dropped,
    )
