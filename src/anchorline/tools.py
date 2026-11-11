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


def build_tools(store: FactStore, session_id: str | None = None) -> dict[str, Callable[..., ToolResult]]:
    def memory_search(
        query: str = "", budget_tokens: int = 2000, limit: int = 20, include_history: bool = False
    ) -> ToolResult:
        # 混合检索（BM25 + 向量 + RRF + rerank）；不可用时回退纯文本。recalls 供 trace 展示。
        recalls: list[dict] = []
        try:
            from anchorline.retrieval.hybrid import hybrid_search_with_recalls

            facts, recalls = hybrid_search_with_recalls(store.db, query, top_k=limit) if query else ([], [])
        except Exception:
            facts = store.search_text(query, limit=limit) if query else []
        # 回溯意图：把已失效的历史事实也带出来（retrospective 题必须能取到旧值）
        if include_history and query:
            try:
                from sqlalchemy import select

                from anchorline.models import Fact as FactModel
                from anchorline.retrieval.hybrid import tokenize

                q_tokens = set(tokenize(query))
                hist = list(store.db.scalars(select(FactModel).where(FactModel.valid_to.isnot(None)).limit(200)))
                if q_tokens:
                    hist = [f for f in hist if q_tokens & set(tokenize(f"{f.attribute} {f.value}"))]
                seen = {f.id for f in facts}
                facts = facts + [f for f in hist[:limit] if f.id not in seen]
            except Exception:
                pass
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
            meta={
                "used_tokens": asm.used_tokens,
                "hits": len(facts),
                "dropped": len(asm.dropped_items),
                "recalls": recalls,
            },
        )

    def memory_write(
        entity_id: str,
        attribute: str,
        value: str,
        valid_from: str | None = None,
        confidence: float = 1.0,
        source_session_id: str | None = None,
        supersedes_id: str | None = None,
        conflict_type: str | None = None,
    ) -> ToolResult:
        # 记忆的「生效时间」= 写入/记录时间（会话时间），不是对话里提到的事件日期；
        # 事件日期应保留在 value 文本中（如 "25:50（日期 2023-05-30）"）。
        record_time = datetime.now()
        # D6：记录本轮激活的技能名（ACTIVE_SKILLS 由 _run_agent 设置），供记忆页追溯
        from anchorline.skills.context import ACTIVE_SKILLS

        _active = ACTIVE_SKILLS.get() or []
        skill_name = _active[0] if _active else None
        # 显式 supersedes 交给 FactStore.write 统一处理（同一事务里失效旧事实 + 建链）
        fact = store.write(
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            valid_from=record_time,
            confidence=confidence,
            source_session_id=source_session_id or session_id,
            conflict_type=conflict_type,
            supersedes_id=supersedes_id,
            skill_name=skill_name,
        )
        # 同步向量索引（失败不影响写入）
        try:
            from anchorline.retrieval import facts_index

            facts_index.upsert_fact(fact)
        except Exception:
            pass
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

    def kb_search(query: str = "", game: str = "", top_k: int = 3) -> ToolResult:
        """查 LoreKeeper 知识库（wiki 页面级）；与 memory_search（事实记忆）分工。"""
        try:
            from anchorline.retrieval.lorekeeper_kb import search as kb_search_fn

            hits = kb_search_fn(query, game or None, top_k)
        except Exception:
            hits = []
        if not hits:
            return ToolResult(ok=True, content="(no knowledge hit)", meta={"hits": 0})
        text = "\n\n".join(f"[{h['game']}] {h['page_title']}\n{h['text'][:800]}" for h in hits)
        return ToolResult(
            ok=True,
            content=text,
            meta={"hits": len(hits), "pages": [h["page_title"] for h in hits]},
        )

    return {
        "memory_search": memory_search,
        "memory_write": memory_write,
        "memory_forget": memory_forget,
        "kb_search": kb_search,
    }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search the memory store under a token budget. Pass include_history=true when the question asks about a past/initial value (retrospective), so invalidated history is returned too.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "budget_tokens": {"type": "integer", "default": 2000},
                    "include_history": {"type": "boolean", "default": False, "description": "回溯题用：把已失效的历史事实也带出来"},
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
                    "conflict_type": {
                        "type": "string",
                        "enum": ["时效", "语义", "偏好反转", "无"],
                        "description": "可选：这次写入与旧值的冲突类型",
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
    {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": "Search the LoreKeeper game wiki knowledge base (page-level chunks). Use for factual game questions (characters/items/mechanics); use memory_search for personal memories/facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "game": {"type": "string", "enum": ["sr", "ys", "zzz"], "description": "可选：sr=崩坏星穹铁道, ys=原神, zzz=绝区零；留空则三库都查"},
                    "top_k": {"type": "integer", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
]
