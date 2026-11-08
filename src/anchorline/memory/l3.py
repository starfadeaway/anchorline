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
