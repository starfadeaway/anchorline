# -*- coding: utf-8 -*-
"""FastAPI 入口（M1 最小）：health + memory search/write + trace 查询 + SSE 聊天占位。

单 API 副本；SSE 聊天在 M1 后半段接入 LangGraph，当前先返回 501 并保留路由形态。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from anchorline import __version__
from anchorline.db import get_db
from anchorline.memory.l3 import assemble, ContextItem
from anchorline.memory.store import FactStore
from anchorline.models import Trace

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


@app.post("/chat")
async def chat() -> StreamingResponse:
    async def _gen():
        yield "event: error\ndata: " + json.dumps({"detail": "chat 在 M1 后半段接入 LangGraph 后启用"}) + "\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
