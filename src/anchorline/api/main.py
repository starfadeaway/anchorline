# -*- coding: utf-8 -*-
"""FastAPI 入口：health / memory / trace / 真实 tool-calling 聊天（SSE）。

聊天路径：LangGraph bounded agent loop（`graph/chat.py`）→ 模型（DeepSeek）
通过 function calling 调用 `memory_search / memory_write / memory_forget`。
评测模式不走这里（评测用固定工具路径的 harness）。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from anchorline import __version__
from anchorline.db import get_db
from anchorline.graph.chat import Bounds, build_chat_graph, initial_state
from anchorline.llm import reader_client
from anchorline.memory.l3 import ContextItem, assemble
from anchorline.memory.store import FactStore
from anchorline.models import Trace
from anchorline.tools import TOOL_SCHEMAS

app = FastAPI(title="Anchorline", version=__version__)


class SearchRequest(BaseModel):
    query: str = ""
    budget_tokens: int = Field(default=2000, ge=1, le=32000)
    limit: int = Field(default=20, ge=1, le=100)


class SearchResponse(BaseModel):
    text: str
    used_tokens: int
    hits: int


class WriteRequest(BaseModel):
    entity_id: str
    attribute: str
    value: str
    valid_from: datetime | None = None
    confidence: float = 1.0
    source_session_id: str | None = None


class WriteResponse(BaseModel):
    fact_id: str
    supersedes: str | None = None


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    max_steps: int = Field(default=6, ge=1, le=16)


class ChatResponse(BaseModel):
    answer: str
    stop_reason: str
    steps: int
    tool_calls: list[dict[str, Any]]


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_ok = False
        detail = str(exc)
    else:
        detail = ""
    return {"status": "ok" if db_ok else "degraded", "version": __version__, "db": db_ok, "detail": detail}


@app.post("/memory/search", response_model=SearchResponse)
def memory_search(req: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    store = FactStore(db)
    facts = store.search_text(req.query, limit=req.limit) if req.query else []
    items = [
        ContextItem(
            text=f"[{f.id[:8]}] {f.entity_id}.{f.attribute} = {f.value}",
            score=f.confidence,
            source_id=f.id,
        )
        for f in facts
    ]
    asm = assemble(items, req.budget_tokens)
    db.add(Trace(
        session_id=None,
        query=req.query,
        budget_tokens=req.budget_tokens,
        used_tokens=asm.used_tokens,
        layers="L2>L3",
        injected_fact_ids=json.dumps([i.source_id for i in asm.used_items]),
    ))
    db.commit()
    return SearchResponse(text=asm.text, used_tokens=asm.used_tokens, hits=len(facts))


@app.post("/memory/write", response_model=WriteResponse)
def memory_write(req: WriteRequest, db: Session = Depends(get_db)) -> WriteResponse:
    store = FactStore(db)
    fact = store.write(
        entity_id=req.entity_id,
        attribute=req.attribute,
        value=req.value,
        valid_from=req.valid_from or datetime.now(),
        confidence=req.confidence,
        source_session_id=req.source_session_id,
    )
    db.commit()
    return WriteResponse(fact_id=fact.id, supersedes=fact.supersedes_id)


@app.get("/trace/{trace_id}")
def get_trace(trace_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.get(Trace, trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return {
        "id": row.id,
        "query": row.query,
        "budget_tokens": row.budget_tokens,
        "used_tokens": row.used_tokens,
        "layers": row.layers,
        "injected_fact_ids": row.injected_fact_ids,
    }


def _run_agent(messages: list[dict], db: Session, max_steps: int):
    store = FactStore(db)
    reader = reader_client()

    def model_fn(msgs: list[dict]) -> dict:
        return reader.complete_with_tools(msgs, TOOL_SCHEMAS, max_tokens=2048)

    graph = build_chat_graph(
        store,
        model_fn,
        Bounds(max_steps=max_steps, max_tokens=24000, wall_time_s=180.0),
    )
    out = graph.invoke(
        initial_state(messages),
        {"configurable": {"thread_id": uuid.uuid4().hex}},
    )
    db.commit()
    return out


def _extract_tool_calls(out: dict) -> list[dict[str, Any]]:
    calls = []
    for m in out["messages"]:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            calls.append({
                "name": fn.get("name") or tc.get("name"),
                "arguments": fn.get("arguments") or tc.get("arguments"),
            })
    return calls


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    out = _run_agent(req.messages, db, req.max_steps)
    finals = [m for m in out["messages"] if m.get("role") == "assistant" and (m.get("content") or "").strip()]
    answer = finals[-1]["content"] if finals else ""
    return ChatResponse(answer=answer, stop_reason=out.get("stop_reason", ""), steps=out["steps"], tool_calls=_extract_tool_calls(out))


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """SSE：先逐条推 tool 事件，最后推 answer。"""

    def _gen():
        out = _run_agent(req.messages, db, req.max_steps)
        for tc in _extract_tool_calls(out):
            yield "event: tool\ndata: " + json.dumps(tc, ensure_ascii=False) + "\n\n"
        finals = [m for m in out["messages"] if m.get("role") == "assistant" and (m.get("content") or "").strip()]
        answer = finals[-1]["content"] if finals else ""
        yield "event: final\ndata: " + json.dumps({"answer": answer, "stop_reason": out.get("stop_reason", ""), "steps": out["steps"]}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
