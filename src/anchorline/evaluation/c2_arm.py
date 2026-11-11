# -*- coding: utf-8 -*-
"""C2 臂：a11y-only + 我方 L0 去重 + 我方 4k 组装。

与 B 臂的唯一差异（2×2 设计）：
  - 输入模态：相同（只 a11y，不含 action/thought）；
  - 检索：相同（官方 raw_state_slice 索引，radius=1，top-6）；
  - **压缩/组装：不同**——C2 对切片的 a11y 文本做 L0 跨 state 行级去重，再按 4k 预算组装；
  - B 则直接注入官方的 State 块（URL/Action/AXTree 原文，不去重）。

因此 B → C2 的差值 = 「压缩层」的贡献。
"""
from __future__ import annotations

from dataclasses import dataclass

from anchorline.evaluation.baseline_arm import retrieve
from anchorline.evaluation.reader import build_messages
from anchorline.llm import ChatClient, EmbeddingClient
from anchorline.memory.l0 import L0Deduper
from anchorline.memory.l3 import assemble_blocks
from anchorline.retrieval.baseline import DEFAULT_TOP_K


@dataclass
class C2Result:
    answer: str
    hits: list[dict]
    context_tokens: int
    question: str
    dropped_blocks: int = 0


def answer_c2(
    reader: ChatClient,
    embedder: EmbeddingClient,
    tbl,
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    temperature: float = 1.0,
    max_tokens: int = 8192,
    context_budget_tokens: int = 4000,
) -> C2Result:
    hits = retrieve(tbl, embedder, question, top_k=top_k)
    # L0：按检索顺序跨切片做行级去重（同一轨迹/页面的重复 a11y 行只保留首次）
    deduper = L0Deduper()
    blocks: list[tuple[float, str]] = []
    for h in hits:
        sim = 1.0 - float(h.get("_distance") or 0.0)
        novel = deduper.feed(h.get("axtree_text") or "")
        if novel:
            blocks.append((sim, f"### C2 slice\n- Trajectory: {h['traj_id']}\n- Center state: {h['center']}\n- Similarity (1 − L2 距离，非余弦): {sim:.4f}\n\n" + "\n".join(novel)))
    context, used_tokens, dropped = assemble_blocks(blocks, context_budget_tokens)
    context = context or "(empty)"
    messages = build_messages(question, context)
    answer = reader.complete(messages, temperature=temperature, max_tokens=max_tokens)
    if not answer.strip():
        answer = reader.complete(messages, temperature=temperature, max_tokens=max_tokens * 2)
    return C2Result(
        answer=answer,
        hits=hits,
        context_tokens=used_tokens,
        question=question,
        dropped_blocks=dropped,
    )
