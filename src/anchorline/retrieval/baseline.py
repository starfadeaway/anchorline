# -*- coding: utf-8 -*-
"""官方基线臂（B 臂）的切片与上下文构造。

规则来自官方 `memory_modules/agentrunbook_r.py`（已读一手源码）：
  - `DEFAULT_RAW_STATE_SLICE_RADIUS = 1`，`DEFAULT_RAW_STATE_TOP_K = 6`；
  - 每个 center state 一个 entry：slice = states[center-1 : center+2]；
  - **检索面** = `slice_axtree_text`（相邻 state 的 a11y 原文拼接，不做行级去重）；
  - **注入面** = State 块（URL / Action / AXTree），**不含 thought**；
  - 完整动作序列与局部动作序列一并注入（官方 `_build_raw_state_context_items` 的形态）。

注意：v0.8 §6.8 第 16 条「官方基线检索面只有 a11y 树」说的是**检索面**；
官方注入的 State 块里带 Action 字段，本实现照此。
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SLICE_RADIUS = 1
DEFAULT_TOP_K = 6
EMBEDDING_PRETOKEN_CHAR_CAP = 40000  # 官方常量
QUERY_INSTRUCTION = (
    "Given a question about past agent trajectories, retrieve relevant memory entries that help answer it."
)


def truncate_middle(text: str, max_chars: int) -> str:
    """官方 `_truncate_middle` 的同一实现：截中间、保留头尾。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 64:
        return text[:max_chars]
    omitted = len(text) - max_chars
    marker = f"\n...[truncated {omitted} chars]...\n"
    if len(marker) >= max_chars:
        return text[:max_chars]
    head = (max_chars - len(marker)) // 2
    tail = max_chars - len(marker) - head
    return f"{text[:head].rstrip()}{marker}{text[-tail:].lstrip()}".strip()


def format_query_for_embedding(query: str) -> str:
    """官方 `_format_query_for_embedding`：查询侧加 Instruct 前缀。"""
    return f"Instruct: {QUERY_INSTRUCTION}\nQuery:{query.strip()}".strip()


def axtree_of(state: dict) -> str:
    text = state.get("accessibility_tree")
    if isinstance(text, str):
        return text
    alt = state.get("text")
    return alt if isinstance(alt, str) else ""


def _state_url(state: dict) -> str:
    return str(state.get("url") or "")


def _state_action(state: dict) -> str:
    value = state.get("action")
    return value if isinstance(value, str) and value.strip() else "<none>"


@dataclass(frozen=True)
class SliceEntry:
    entry_id: str
    trajectory_id: str
    center_state_index: int
    slice_state_indexes: tuple[int, ...]
    axtree_text: str  # 检索面
    state_blocks: str  # 注入面（URL / Action / AXTree）


def normalize_vector(vec: list[float]) -> list[float]:
    """L2 归一化（官方 `_normalize_embeddings` 同口径），使 l2 排序等价 cosine。"""
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def build_entries(trajectory: dict, radius: int = DEFAULT_SLICE_RADIUS) -> list[SliceEntry]:
    states = [s for s in (trajectory.get("states") or []) if isinstance(s, dict)]
    tid = str(trajectory.get("id"))
    n = len(states)
    entries: list[SliceEntry] = []
    for c in range(n):
        idxs = tuple(range(max(0, c - radius), min(n, c + radius + 1)))
        axtree = "\n\n".join(axtree_of(states[j]) for j in idxs)
        blocks = "\n\n".join(
            f"State {j} (step {j})\n- URL: {_state_url(states[j])}\n- Action: {_state_action(states[j])}\n"
            f"- AXTree:\n{axtree_of(states[j])}"
            for j in idxs
        )
        entries.append(
            SliceEntry(
                entry_id=f"{tid}:raw_state:{c:04d}",
                trajectory_id=tid,
                center_state_index=c,
                slice_state_indexes=idxs,
                axtree_text=axtree,
                state_blocks=blocks,
            )
        )
    return entries
