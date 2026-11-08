# -*- coding: utf-8 -*-
"""L3 预算内召回 / 组装。

口径（v0.8 §5 / §6.4）：
  - 预算档 2k / 4k / 8k tokens；
  - 先按 score（召回分）再按时间新近度排序，逐条填充直到预算用尽；
  - **不做「预算不够就静默丢最重要那条」**：按排序顺序保留，被裁掉的写入 trace；
  - token 估算暂用 chars/4（与 `measure_compression.py` 一致），pilot 阶段用真实 tokenizer 校准。
"""
from __future__ import annotations

from dataclasses import dataclass, field

CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class ContextItem:
    text: str
    score: float = 0.0
    kind: str = "fact"  # fact / event / message
    source_id: str | None = None


@dataclass
class AssemblyResult:
    text: str
    used_tokens: int
    used_items: list[ContextItem] = field(default_factory=list)
    dropped_items: list[ContextItem] = field(default_factory=list)


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def assemble(items: list[ContextItem], budget_tokens: int) -> AssemblyResult:
    """按 score 降序把 items 填入预算；返回文本与 token 占用。"""
    if budget_tokens <= 0:
        return AssemblyResult(text="", used_tokens=0, dropped_items=list(items))

    ordered = sorted(enumerate(items), key=lambda kv: (-kv[1].score, kv[0]))
    used: list[ContextItem] = []
    dropped: list[ContextItem] = []
    blocks: list[str] = []
    used_tokens = 0

    for _, item in ordered:
        text = item.text.strip()
        if not text:
            continue
        cost = estimate_tokens(text) + 1  # 换行分隔
        if used_tokens + cost > budget_tokens:
            dropped.append(item)
            continue
        used.append(item)
        blocks.append(text)
        used_tokens += cost

    return AssemblyResult(text="\n\n".join(blocks), used_tokens=used_tokens, used_items=used, dropped_items=dropped)


def assemble_blocks(
    blocks: list[tuple[float, str]],
    budget_tokens: int,
    *,
    chars_per_token: int = CHARS_PER_TOKEN,
) -> tuple[str, int, int]:
    """长文本块（B 臂切片 / D 臂 state 条目）的预算组装。

    与 `assemble` 的区别：单个块可能远超预算，**截断到剩余预算而不是整块丢弃**
    （同官方 `truncate_memory_context` 语义）。B 臂与 D 臂共用本函数，保证预算口径一致。

    参数:
        blocks: [(score, text)]；score 越大越优先。
        budget_tokens: token 预算（按 chars_per_token 折算成字符）。
    返回:
        (组装后的文本, 实际用掉的 tokens, 被完全丢弃的块数)
    """
    if budget_tokens <= 0:
        return "", 0, len(blocks)

    budget_chars = budget_tokens * chars_per_token
    used_chars = 0
    dropped = 0
    parts: list[str] = []
    for _, block in sorted(blocks, key=lambda sb: -sb[0]):
        text = block.strip()
        if not text:
            continue
        if used_chars >= budget_chars:
            dropped += 1
            continue
        remain = budget_chars - used_chars
        if len(text) <= remain:
            parts.append(text)
            used_chars += len(text)
        else:
            parts.append(text[:remain])
            used_chars += remain
    return ("\n\n".join(parts) if parts else ""), used_chars // chars_per_token, dropped
