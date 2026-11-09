# -*- coding: utf-8 -*-
"""FastAPI 入口：health / memory / trace / 真实 tool-calling 聊天（SSE）。

聊天路径：LangGraph bounded agent loop（`graph/chat.py`）→ 模型（DeepSeek）
通过 function calling 调用 `memory_search / memory_write / memory_forget`。
评测模式不走这里（评测用固定工具路径的 harness）。
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from anchorline import __version__
from anchorline.db import get_db
from anchorline.graph.chat import Bounds, build_chat_graph, initial_state
from anchorline.llm import chat_client, reader_client
from anchorline.memory.l3 import ContextItem, assemble
from anchorline.memory.store import FactStore
from anchorline.models import Fact, Message, Session as ChatSession, Trace
from anchorline.tools import TOOL_SCHEMAS

log = logging.getLogger("anchorline.api")

# src/anchorline/api/main.py -> api -> anchorline -> src -> 仓库根
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVAL_DIR = os.path.join(ROOT, "data", "eval")

app = FastAPI(title="Anchorline", version=__version__)


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """兜底：未处理异常返回 JSON，不把堆栈/DSN 暴露给前端；前端有错误提示。"""
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "内部错误，请稍后重试（详情已记录日志）"})


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
    session_id: str | None = None  # 为空则新建会话（聊天模式有会话列表）
    model: str = "deepseek"  # 聊天模式可切换 deepseek / minimax；评测模式固定


class ChatResponse(BaseModel):
    answer: str
    stop_reason: str
    steps: int
    tool_calls: list[dict[str, Any]]
    trace_id: int | None = None
    session_id: str | None = None
    meta: dict[str, Any] = {}


class FactOut(BaseModel):
    id: str
    entity_id: str
    attribute: str
    value: str
    valid_from: datetime
    valid_to: datetime | None
    confidence: float
    supersedes_id: str | None
    fact_type: str
    conflict_type: str | None


@app.get("/memory/facts", response_model=list[FactOut])
def list_facts(
    entity_id: str | None = None,
    attribute: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[FactOut]:
    """记忆浏览器：分页列出事实（当前值与历史都返回，valid_to 为空才是当前值）。"""
    from sqlalchemy import select

    stmt = select(Fact).order_by(Fact.created_at.desc()).limit(limit).offset(offset)
    if entity_id:
        stmt = stmt.where(Fact.entity_id == entity_id)
    if attribute:
        stmt = stmt.where(Fact.attribute.like(f"%{attribute}%"))
    rows = list(db.scalars(stmt))
    return [
        FactOut(
            id=f.id,
            entity_id=f.entity_id,
            attribute=f.attribute,
            value=f.value,
            valid_from=f.valid_from,
            valid_to=f.valid_to,
            confidence=f.confidence,
            supersedes_id=f.supersedes_id,
            fact_type=f.fact_type,
            conflict_type=f.conflict_type,
        )
        for f in rows
    ]


@app.get("/memory/facts/{fact_id}/history", response_model=list[FactOut])
def fact_history(fact_id: str, db: Session = Depends(get_db)) -> list[FactOut]:
    """某条事实同一 (entity, attribute) 的完整历史（含被 supersede 的旧值）。"""
    anchor = db.get(Fact, fact_id)
    if anchor is None:
        raise HTTPException(status_code=404, detail="fact not found")
    rows = FactStore(db).history(anchor.entity_id, anchor.attribute)
    return [
        FactOut(
            id=f.id,
            entity_id=f.entity_id,
            attribute=f.attribute,
            value=f.value,
            valid_from=f.valid_from,
            valid_to=f.valid_to,
            confidence=f.confidence,
            supersedes_id=f.supersedes_id,
            fact_type=f.fact_type,
            conflict_type=f.conflict_type,
        )
        for f in rows
    ]


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """健康检查：数据库不可用时**不回显异常原文**（异常里可能带 DSN/密码）。"""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "db": db_ok,
        "detail": "" if db_ok else "database connection failed (details redacted)",
    }


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


def _run_agent(
    messages: list[dict],
    db: Session,
    max_steps: int,
    model: str = "deepseek",
    session_id: str | None = None,
):
    """跑一轮 LangGraph agent，并把本轮召回/工具调用写入 traces（供前端 Trace 面板）。"""
    t0 = time.time()
    store = FactStore(db)
    reader = chat_client(model)

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

    query = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")
    tool_calls = _extract_tool_calls(out)
    trace = Trace(
        session_id=session_id,
        query=str(query)[:2000],
        budget_tokens=0,
        used_tokens=sum(len(str(m.get("content") or "")) for m in out["messages"]) // 4,
        # layers 同时编码步数，便于按会话恢复时显示 steps（避免新增列迁移）
        layers=f"chat>tools;steps={out.get('steps', 0)}",
        injected_fact_ids=json.dumps(tool_calls, ensure_ascii=False),
        resolution=out.get("stop_reason", ""),
    )
    db.add(trace)
    db.commit()
    out["trace_id"] = trace.id
    out["duration_ms"] = int((time.time() - t0) * 1000)
    out["total_tokens"] = sum(len(str(m.get("content") or "")) for m in out["messages"]) // 4
    out["tool_errors"] = sum(
        1
        for m in out["messages"]
        if m.get("role") == "tool" and str(m.get("content") or "").startswith("tool error")
    )
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
    # 先确定会话（trace 需要 session_id，页面切换后 trace 也能按会话找回）
    is_new = not req.session_id
    sid = req.session_id
    try:
        if not sid:
            s = ChatSession(domain="chat")
            db.add(s)
            db.flush()
            sid = s.id
        elif db.get(ChatSession, sid) is None:
            db.add(ChatSession(id=sid, domain="chat"))
            db.flush()
    except Exception:
        log.exception("failed to create chat session")
        db.rollback()
        sid = req.session_id

    try:
        out = _run_agent(req.messages, db, req.max_steps, model=req.model, session_id=sid)
    except HTTPException:
        raise
    except Exception as exc:  # 模型/DB 抖动：转成 502，前端弹窗提示而不是整页崩
        log.exception("chat failed")
        raise HTTPException(status_code=502, detail=f"聊天服务暂时不可用（{type(exc).__name__}），请重试") from exc
    finals = [m for m in out["messages"] if m.get("role") == "assistant" and (m.get("content") or "").strip()]
    answer = finals[-1]["content"] if finals else ""

    # 会话消息落库（失败不影响本轮回答）
    try:
        last_user = next((m for m in reversed(req.messages) if m.get("role") == "user"), None)
        if last_user:
            db.add(Message(session_id=sid, role="user", content=str(last_user.get("content") or "")[:8000]))
        db.add(Message(session_id=sid, role="assistant", content=str(answer or "")[:8000]))
        # 会话主题：新会话或 topic 为空的旧会话，都用模型生成（替代硬编码关键词分组）
        session_row = db.get(ChatSession, sid)
        if last_user and session_row is not None and not session_row.topic:
            topic = _gen_topic(str(last_user.get("content") or ""), req.model)
            if topic:
                session_row.topic = topic
        db.commit()
    except Exception:
        log.exception("failed to persist chat session")
        db.rollback()

    return ChatResponse(
        answer=answer,
        stop_reason=out.get("stop_reason", ""),
        steps=out["steps"],
        tool_calls=_extract_tool_calls(out),
        trace_id=out.get("trace_id"),
        session_id=sid,
        meta={
            "model": req.model,
            "duration_ms": out.get("duration_ms"),
            "total_tokens": out.get("total_tokens"),
            "tool_errors": out.get("tool_errors", 0),
            "run_id": str(out.get("trace_id") or ""),
        },
    )


class SessionOut(BaseModel):
    id: str
    title: str
    topic: str | None = None
    created_at: datetime
    message_count: int


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


@app.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)) -> list[SessionOut]:
    """聊天会话列表（左侧栏）；标题取首条 user 消息。"""
    rows = list(
        db.scalars(
            select(ChatSession).where(ChatSession.domain == "chat").order_by(ChatSession.created_at.desc()).limit(50)
        )
    )
    out: list[SessionOut] = []
    for s in rows:
        msgs = list(db.scalars(select(Message).where(Message.session_id == s.id).order_by(Message.id)))
        first_user = next((m for m in msgs if m.role == "user"), None)
        title = (first_user.content.strip()[:60] if first_user else "（空会话）")
        out.append(SessionOut(id=s.id, title=title, topic=s.topic, created_at=s.created_at, message_count=len(msgs)))
    return out


@app.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def session_messages(session_id: str, db: Session = Depends(get_db)) -> list[MessageOut]:
    if db.get(ChatSession, session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    rows = list(db.scalars(select(Message).where(Message.session_id == session_id).order_by(Message.id)))
    return [MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in rows]


@app.post("/sessions")
def create_session(db: Session = Depends(get_db)) -> dict[str, str]:
    s = ChatSession(domain="chat")
    db.add(s)
    db.commit()
    return {"id": s.id}


class TraceOut(BaseModel):
    id: int
    query: str
    layers: str
    used_tokens: int
    resolution: str | None
    injected_fact_ids: str | None
    created_at: datetime
    steps: int = 0


def _trace_out(r: Trace) -> TraceOut:
    steps = 0
    for part in (r.layers or "").split(";"):
        if part.startswith("steps="):
            try:
                steps = int(part.split("=", 1)[1] or 0)
            except ValueError:
                steps = 0
    return TraceOut(
        id=r.id,
        query=r.query,
        layers=r.layers,
        used_tokens=r.used_tokens,
        resolution=r.resolution,
        injected_fact_ids=r.injected_fact_ids,
        created_at=r.created_at,
        steps=steps,
    )


@app.get("/sessions/{session_id}/traces", response_model=list[TraceOut])
def session_traces(session_id: str, db: Session = Depends(get_db)) -> list[TraceOut]:
    """按会话取最近的 trace（切换页面/会话后仍能找回）。"""
    rows = list(
        db.scalars(select(Trace).where(Trace.session_id == session_id).order_by(Trace.id.desc()).limit(20))
    )
    return [_trace_out(r) for r in rows]


@app.get("/traces", response_model=list[TraceOut])
def list_traces(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)) -> list[TraceOut]:
    """全局最近 trace（记忆页画资源消耗图表用）。"""
    rows = list(db.scalars(select(Trace).order_by(Trace.id.desc()).limit(limit)))
    return [_trace_out(r) for r in rows]


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """删除会话及其消息（记忆事实不受影响）。"""
    if db.get(ChatSession, session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    db.execute(delete(Message).where(Message.session_id == session_id))
    db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    db.commit()
    return {"deleted": session_id}


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """SSE：先逐条推 tool 事件，最后推 answer；出错推 error 事件而不是断开无声。"""

    def _gen():
        try:
            out = _run_agent(req.messages, db, req.max_steps, model=req.model, session_id=req.session_id)
            for tc in _extract_tool_calls(out):
                yield "event: tool\ndata: " + json.dumps(tc, ensure_ascii=False) + "\n\n"
            finals = [m for m in out["messages"] if m.get("role") == "assistant" and (m.get("content") or "").strip()]
            answer = finals[-1]["content"] if finals else ""
            yield "event: final\ndata: " + json.dumps({"answer": answer, "stop_reason": out.get("stop_reason", ""), "steps": out["steps"]}, ensure_ascii=False) + "\n\n"
        except Exception as exc:
            log.exception("chat stream failed")
            yield "event: error\ndata: " + json.dumps({"detail": f"{type(exc).__name__}: 生成失败"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


# ---------------------------------------------------------------- 写接口（前端记忆页）

class ForgetRequest(BaseModel):
    entity_id: str
    attribute: str
    at: datetime | None = None


class FactPatch(BaseModel):
    value: str | None = None
    confidence: float | None = None


def _gen_topic(text: str, model: str) -> str:
    """用模型给会话生成 2-4 字主题标签（替代硬编码关键词，新领域也能归类）。"""
    try:
        client = chat_client(model)
        out = client.complete(
            [
                {
                    "role": "system",
                    "content": "你是会话主题分类器。用 2-4 个汉字概括用户这段话的主题（如：跑步、游泳、乒乓球、饮食、工作）。只输出主题词，不要标点、不要解释。",
                },
                {"role": "user", "content": str(text)[:400]},
            ],
            temperature=0.0,
            max_tokens=16,
        )
        return (out or "").strip().replace("\n", "").strip("。.，,：:")[:16]
    except Exception:
        log.exception("topic generation failed")
        return ""


@app.delete("/memory/facts/{fact_id}")
def delete_fact(fact_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """物理删除一条记忆（用于控制存储量；其他事实不受影响）。"""
    fact = db.get(Fact, fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="fact not found")
    db.delete(fact)
    db.commit()
    return {"deleted": fact_id}


@app.delete("/memory/facts")
def purge_stale_facts(db: Session = Depends(get_db)) -> dict[str, int]:
    """批量清理已失效事实（控制存储量，保留当前值）。"""
    rows = list(db.scalars(select(Fact).where(Fact.valid_to.isnot(None))))
    ids = [f.id for f in rows]
    if ids:
        db.execute(delete(Fact).where(Fact.id.in_(ids)))
        db.commit()
    return {"deleted": len(ids)}


class SettingsOut(BaseModel):
    version: str
    db_ok: bool
    reader_model: str
    judge_model: str
    embedding_model: str
    rerank_model: str
    budgets: list[int]
    # 聊天模式可切换的 provider（评测模式固定，见 m3_summary）
    minimax_model: str
    minimax_base_url: str
    chat_models: list[str]


class EvalArmOut(BaseModel):
    arm: str
    accuracy: float
    n: int
    source: str
    note: str | None = None


@app.post("/memory/forget")
def forget(req: ForgetRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """按 entity+attribute 标记失效（不物理删除，保留历史）。"""
    try:
        fact = FactStore(db).forget(req.entity_id, req.attribute, at=req.at)
    except Exception as exc:
        log.exception("forget failed")
        raise HTTPException(status_code=500, detail="标记失效失败") from exc
    if fact is None:
        raise HTTPException(status_code=404, detail="未找到该事实")
    return {"fact_id": fact.id}


@app.post("/memory/facts/{fact_id}/invalidate")
def invalidate_fact(fact_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    fact = db.get(Fact, fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="fact not found")
    if fact.valid_to is None:  # 幂等：已失效的不重复写
        fact.valid_to = datetime.now(timezone.utc)
        db.commit()
    return {"fact_id": fact.id}


@app.patch("/memory/facts/{fact_id}")
def patch_fact(fact_id: str, body: FactPatch, db: Session = Depends(get_db)) -> dict[str, str]:
    fact = db.get(Fact, fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="fact not found")
    if body.value is not None:
        fact.value = body.value
    if body.confidence is not None:
        fact.confidence = body.confidence
    db.commit()
    return {"fact_id": fact.id}


@app.get("/settings", response_model=SettingsOut)
def settings_view(db: Session = Depends(get_db)) -> SettingsOut:
    """只读配置（脱敏）：模型名与预算，不含任何 key。"""
    from anchorline.config import Settings

    s = Settings()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return SettingsOut(
        version=__version__,
        db_ok=db_ok,
        reader_model=s.deepseek_reader_model,
        judge_model=s.deepseek_judge_model,
        embedding_model=s.siliconflow_embedding_model,
        rerank_model=s.siliconflow_rerank_model,
        budgets=[4000, 8000, 16000],
        minimax_model=s.minimax_model,
        minimax_base_url=s.minimax_base_url,
        chat_models=["deepseek", "minimax"],
    )


def _load_eval(name: str) -> dict | None:
    path = os.path.join(EVAL_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception("failed to read eval file %s", path)
        return None


@app.get("/eval/summary", response_model=list[EvalArmOut])
def eval_summary() -> list[EvalArmOut]:
    """把 data/eval 下的结果汇总成臂级表；文件缺失/损坏只跳过，不抛 500。"""
    out: list[EvalArmOut] = []
    b154 = _load_eval("b_arm_154_v2.json")
    if b154:
        rows = b154.get("per_question", [])
        out.append(EvalArmOut(
            arm="B（官方基线）", n=len(rows),
            accuracy=sum(r["mean"] for r in rows) / max(1, len(rows)),
            source="b_arm_154_v2.json", note="154 题确定性判分，1 次/题",
        ))
    for fname, arm, key, note in [
        ("d_arm_154_v2.json", "D（完整轨迹+L0，单 state）", "d_accuracy", "154 题，1 次/题"),
        ("d_arm_154_neighbor.json", "D（state+邻居）", "d_accuracy", "154 题，检验检索粒度"),
        ("c2_arm_154.json", "C2（a11y-only+L0）", "c2_accuracy", "154 题，压缩层单变量"),
    ]:
        d = _load_eval(fname)
        if d and key in d:
            n = int(
                d.get("n_questions")
                or (d.get("config") or {}).get("n_questions")
                or len(d.get("per_question", []))
            )
            out.append(EvalArmOut(
                arm=arm, accuracy=float(d[key]), n=n,
                source=fname, note=note,
            ))
    a168 = _load_eval("arm_168.json")
    if a168:
        n = int(a168.get("n_common", 0))
        out.append(EvalArmOut(arm="B（168）", accuracy=float(a168["b_accuracy"]), n=n,
                              source="arm_168.json", note="154 + 14 judge（3 题 judge 缺失已排除）"))
        out.append(EvalArmOut(arm="D（168）", accuracy=float(a168["d_accuracy"]), n=n,
                              source="arm_168.json", note="同上；judge prompt 已冻结"))
    return out
