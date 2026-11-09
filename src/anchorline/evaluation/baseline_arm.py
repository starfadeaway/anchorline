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
from anchorline.memory.l3 import assemble_blocks
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
    dropped_slices: int = 0
    total_hit_tokens: int = 0


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
    max_tokens: int = 8192,
    context_budget_tokens: int = 4000,
) -> BaselineResult:
    hits = retrieve(tbl, embedder, question, top_k=top_k)
    items: list[tuple[float, str]] = []
    for h in hits:
        dist = float(h.get("_distance") or 0.0)
        sim = 1.0 - dist  # 向量已 L2 归一化，l2 与 cosine 单调对应
        block = (
            f"### Raw state result\n"
            f"- Trajectory: {h['traj_id']}\n"
            f"- Goal: {h.get('goal', '')}\n"
            f"- Center state index: {h['center']}\n"
            f"- Similarity: {sim:.4f}\n\n"
            f"Relevant state slices\n{h['state_blocks']}\n"
        )
        items.append((sim, block))
    # B 臂预算档：4k（与 §6.5 的「B 臂 1 档」一致）。
    # 长切片按官方 `truncate_memory_context` 的语义**截断**而不是整块丢弃；
    # 统一走 `assemble_blocks`，与 D 臂共用同一预算口径。
    context, used_tokens, dropped = assemble_blocks(items, context_budget_tokens)
    context = context or "(empty)"
    messages = build_messages(question, context)
    answer = reader.complete(messages, temperature=temperature, max_tokens=max_tokens)
    if not answer.strip():
        # reasoning 模型可能把 token 全花在思考上；空答案时放大上限重试一次
        answer = reader.complete(messages, temperature=temperature, max_tokens=max_tokens * 2)
    return BaselineResult(
        answer=answer,
        hits=hits,
        context_tokens=used_tokens,
        question=question,
        dropped_slices=dropped,
        total_hit_tokens=sum(len(text) // 4 for _, text in items),
    )
