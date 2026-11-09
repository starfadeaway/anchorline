# -*- coding: utf-8 -*-
"""内存工具：memory_search / memory_write / memory_forget（MCP 三工具的本地实现）。

同一套函数既供 LangGraph 聊天/评测路径调用，也供 thin MCP server 暴露 ——
**MCP 与内部路径同源**（v0.8 M1 退出标准）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from anchorline.memory.l3 import ContextItem, assemble
from anchorline.memory.store import FactStore
from anchorline.models import Fact


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str
    meta: dict[str, Any]


def _parse_valid_from(value: str | None) -> datetime:
    if not value:
        return datetime.now()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.now()


def build_tools(store: FactStore) -> dict[str, Callable[..., ToolResult]]:
    def memory_search(query: str = "", budget_tokens: int = 2000, limit: int = 20) -> ToolResult:
        facts = store.search_text(query, limit=limit) if query else []
        items = [
            ContextItem(
                text=f"[{f.id[:8]}] {f.entity_id}.{f.attribute} = {f.value} (valid_from={f.valid_from:%Y-%m-%d %H:%M})",
                score=f.confidence,
                kind="fact",
                source_id=f.id,
            )
            for f in facts
        ]
        asm = assemble(items, budget_tokens)
        return ToolResult(
            ok=True,
            content=asm.text or "(no memory hit)",
            meta={"used_tokens": asm.used_tokens, "hits": len(facts), "dropped": len(asm.dropped_items)},
        )

    def memory_write(
        entity_id: str,
        attribute: str,
        value: str,
        valid_from: str | None = None,
        confidence: float = 1.0,
        source_session_id: str | None = None,
        supersedes_id: str | None = None,
    ) -> ToolResult:
        # 记忆的「生效时间」= 写入/记录时间（会话时间），不是对话里提到的事件日期；
        # 事件日期应保留在 value 文本中（如 "25:50（日期 2023-05-30）"）。
        record_time = datetime.now()
        # 可选：显式指定要覆盖的旧事实（agent 先 search 拿到旧 id，再 write）
        if supersedes_id:
            old = store.db.get(Fact, supersedes_id)
            if old is not None and old.valid_to is None:
                old.valid_to = record_time
                store.db.flush()
        fact = store.write(
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            valid_from=record_time,
            confidence=confidence,
            source_session_id=source_session_id,
        )
        return ToolResult(
            ok=True,
            content=json.dumps(
                {"fact_id": fact.id, "supersedes": fact.supersedes_id, "archived": store.last_archived},
                ensure_ascii=False,
            ),
            meta={"fact_id": fact.id, "archived": store.last_archived},
        )

    def memory_forget(entity_id: str, attribute: str, at: str | None = None) -> ToolResult:
        cur = store.current(entity_id, attribute)
        if cur is None:
            return ToolResult(ok=False, content="fact not found", meta={})
        cur.valid_to = _parse_valid_from(at)
        return ToolResult(ok=True, content=f"marked invalid: {cur.id}", meta={"fact_id": cur.id})

    return {
        "memory_search": memory_search,
        "memory_write": memory_write,
        "memory_forget": memory_forget,
    }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search the memory store under a token budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "budget_tokens": {"type": "integer", "default": 2000},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_write",
            "description": "Write a fact (entity / attribute / value / valid_from). Updating an existing memory: first memory_search, then pass the old fact's supersedes_id so it is invalidated (not deleted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "attribute": {"type": "string"},
                    "value": {"type": "string"},
                    "valid_from": {"type": "string"},
                    "supersedes_id": {
                        "type": "string",
                        "description": "旧事实 id（先 memory_search 取得）；更新已有记忆时传入，旧值会标记失效",
                    },
                },
                "required": ["entity_id", "attribute", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_forget",
            "description": "Mark a fact invalid without deleting it (no physical delete).",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "attribute": {"type": "string"},
                    "at": {"type": "string"},
                },
                "required": ["entity_id", "attribute"],
            },
        },
    },
]
