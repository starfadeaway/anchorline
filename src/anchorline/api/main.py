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
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from anchorline import __version__
from anchorline.config import Settings
from anchorline.db import get_db
from anchorline.graph.chat import Bounds, build_chat_graph, initial_state
from anchorline.llm import chat_client
from anchorline.logging_setup import configure_logging
from anchorline.memory.l3 import ContextItem, assemble
from anchorline.memory.store import FactStore, _attr_tokens
from anchorline.models import Fact, Message, ReviewDecision, Trace
from anchorline.models import Session as ChatSession
from anchorline.tools import TOOL_SCHEMAS

log = logging.getLogger("anchorline.api")

# src/anchorline/api/main.py -> api -> anchorline -> src -> 仓库根
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVAL_DIR = os.path.join(ROOT, "data", "eval")

app = FastAPI(title="Anchorline", version=__version__)
configure_logging()


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    """可选 API token：设置 API_TOKEN 后，除 /health 与文档外都要求 X-API-Token。默认关闭。"""
    token = Settings().api_token
    if token:
        path = request.url.path
        if path not in ("/health", "/docs", "/openapi.json", "/redoc"):
            got = request.headers.get("x-api-token") or request.headers.get("authorization", "")
            got = got.removeprefix("Bearer ").strip()
            if got != token:
                return JSONResponse(status_code=401, content={"detail": "unauthorized: invalid or missing X-API-Token"})
    return await call_next(request)


@app.middleware("http")
async def _timing_middleware(request: Request, call_next):
    """记录每请求耗时/状态（供 /metrics 真实延迟分位数）。"""
    from anchorline.api import metrics

    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        metrics.record(request.url.path, 500, (time.perf_counter() - t0) * 1000)
        raise
    metrics.record(request.url.path, response.status_code, (time.perf_counter() - t0) * 1000)
    return response


@app.get("/metrics", response_model=dict)
def api_metrics() -> dict:
    """最近 1000 请求的延迟分位数 / 错误率 / QPS。"""
    from anchorline.api.metrics import snapshot

    return snapshot()


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
    archived: int = 0
    supersedes: str | None = None


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(min_length=1)
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
    source_session_id: str | None = None
    source_message_id: int | None = None


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
            source_session_id=f.source_session_id,
            source_message_id=f.source_message_id,
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
            source_session_id=f.source_session_id,
            source_message_id=f.source_message_id,
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
    # 混合检索（BM25 + 向量 + RRF + rerank）；不可用时回退纯文本
    try:
        from anchorline.retrieval.hybrid import hybrid_search

        facts = hybrid_search(db, req.query, top_k=req.limit) if req.query else []
    except Exception:
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
    # 同步向量索引（失败不影响写入）
    try:
        from anchorline.retrieval import facts_index

        facts_index.upsert_fact(fact)
    except Exception:
        log.warning("fact index upsert failed", exc_info=True)
    return WriteResponse(fact_id=fact.id, supersedes=fact.supersedes_id, archived=store.last_archived)


class CapacityEntity(BaseModel):
    entity_id: str
    current: int
    stale: int


class CapacityOut(BaseModel):
    limit: int
    total_current: int
    entities: list[CapacityEntity]


@app.get("/memory/capacity", response_model=CapacityOut)
def memory_capacity(db: Session = Depends(get_db)) -> CapacityOut:
    """容量视图：每个实体的当前值/失效数 + 上限（用于前端告警）。"""
    from anchorline.config import Settings

    limit = Settings().memory_max_current_per_entity
    rows = list(db.scalars(select(Fact).order_by(Fact.entity_id)))
    stats: dict[str, list[int]] = {}
    for f in rows:
        cur = stats.setdefault(f.entity_id, [0, 0])
        if f.valid_to is None:
            cur[0] += 1
        else:
            cur[1] += 1
    return CapacityOut(
        limit=limit,
        total_current=sum(v[0] for v in stats.values()),
        entities=[
            CapacityEntity(entity_id=e, current=v[0], stale=v[1])
            for e, v in sorted(stats.items(), key=lambda kv: -kv[1][0])
        ],
    )


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

    query = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")
    # 统一系统约束：实体命名规范 + 不得“口头记住”（必须真的调用 memory_write）
    base_hint = (
        "你是 Anchorline 记忆助手。记忆实体规范：用户本人用 entity_id='user'；"
        "用户的宠物用 'user.宠物名'（如 user.猫）；大模型/AI 工具用 '大模型.名称'（如 大模型.大肥鱼）；"
        "不要把昵称直接当成独立实体。只有真正调用了 memory_write 之后，才能说「已记下/已保存」。"
        "如果用户是在更新之前说过的事实（如人数、成绩、状态变化），必须以最新值回答，并且只保留一条当前值；"
        "同一条信息不要重复写多次，更新时用 supersedes_id 指向旧事实。"
    )
    messages = [{"role": "system", "content": base_hint}, *messages]
    # 回溯意图识别（产品链路）：retrospective 时注入系统提示 + 要求检索历史
    intent = "current"
    if query:
        from anchorline.memory.intent import classify_intent

        intent = classify_intent(str(query), model)
        if intent == "retrospective":
            messages = [
                {
                    "role": "system",
                    "content": (
                        "用户这个问题问的是「过去/最初的值」。回答时请使用历史值："
                        "调用 memory_search 时传 include_history=true 获取已失效的旧记录，不要回答当前值。"
                    ),
                },
                *messages,
            ]

    def model_fn(msgs: list[dict]) -> dict:
        return reader.complete_with_tools(msgs, TOOL_SCHEMAS, max_tokens=2048)

    graph = build_chat_graph(
        store,
        model_fn,
        Bounds(max_steps=max_steps, max_tokens=24000, wall_time_s=180.0),
        session_id=session_id,
    )
    out = graph.invoke(
        initial_state(messages),
        {"configurable": {"thread_id": uuid.uuid4().hex}},
    )

    # 硬校验：本轮写入了新值但最终回答没有体现 → 自动重答一次（防“复读上一轮”）
    out = _verify_and_retry_answer(out, reader)

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
        recalls=json.dumps(out.get("recalls") or [], ensure_ascii=False),
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
    out["intent"] = intent
    out["session_id"] = session_id
    return out


def _verify_and_retry_answer(out: dict[str, Any], reader) -> dict[str, Any]:
    """硬校验：本轮写入了新值但最终回答没有体现 → 用最新值重答一次。

    返回（可能修改过的）out；失败不影响正常回答。
    """
    try:
        write_values: list[str] = []
        for m in out["messages"]:
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                if (fn.get("name") or tc.get("name")) != "memory_write":
                    continue
                raw = fn.get("arguments") or tc.get("arguments") or "{}"
                try:
                    args = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    continue
                v = str((args or {}).get("value") or "").strip()
                if v:
                    write_values.append(v)
        if not write_values:
            return out
        last = next(
            (m for m in reversed(out["messages"]) if m.get("role") == "assistant" and (m.get("content") or "").strip()),
            None,
        )
        answer = str((last or {}).get("content") or "")
        missing: list[str] = []
        for v in write_values:
            toks = re.findall(r"\d+(?:\.\d+)?", v) + re.findall(r"[一二三四五六七八九十百千万]+", v)
            if toks and not any(t in answer for t in toks):
                missing.append(v)
        if missing:
            hint = (
                "你刚才把新的记忆值写入了记忆库：" + "；".join(missing[:3]) + "。"
                "但你的最终回答没有体现这个新值。请基于最新记忆重新回答，必须明确使用新值，不要重复上一轮回答。"
            )
            retry_msgs = [{"role": "system", "content": hint}, *out["messages"]]
            new_answer = reader.complete(retry_msgs, temperature=1.0, max_tokens=2048)
            if new_answer.strip():
                out["messages"] = [m for m in out["messages"] if m is not last] + [
                    {"role": "assistant", "content": new_answer}
                ]
                out["answer_retry"] = True
                log.info("answer retried: missing new values from answer")
    except Exception:
        log.exception("answer verification failed")
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


def _ensure_session(db: Session, sid: str | None) -> str | None:
    """确保会话存在（不存在则创建）；失败返回原值，不阻断聊天。"""
    try:
        if not sid:
            s = ChatSession(domain="chat")
            db.add(s)
            db.flush()
            return s.id
        if db.get(ChatSession, sid) is None:
            db.add(ChatSession(id=sid, domain="chat"))
            db.flush()
        return sid
    except Exception:
        log.exception("failed to create chat session")
        db.rollback()
        return sid


def _persist_turn(
    db: Session, sid: str | None, messages: list[dict], answer: str, model: str
) -> None:
    """落库本轮 user/assistant 消息（主题生成放后台，不阻塞响应）。"""
    if not sid:
        return
    try:
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if last_user:
            db.add(Message(session_id=sid, role="user", content=str(last_user.get("content") or "")[:8000]))
        db.add(Message(session_id=sid, role="assistant", content=str(answer or "")[:8000]))
        db.commit()
    except Exception:
        log.exception("failed to persist chat session")
        db.rollback()


TOPIC_CANON = [
    ("饮食", "饮食偏好"),
    ("跑步", "跑步记录"),
    ("5k", "跑步记录"),
    ("游泳", "游泳记录"),
    ("乒乓", "球类运动"),
    ("球类", "球类运动"),
    ("健身", "健身记录"),
    ("身体", "身体数据"),
    ("模型", "模型与配置"),
    ("游戏", "游戏"),
    ("遗器", "游戏"),
    ("太空", "游戏"),
    ("大肥鱼", "模型与配置"),
    ("deepseek", "模型与配置"),
    ("minimax", "模型与配置"),
    ("配置", "模型与配置"),
    ("宠物", "宠物"),
    ("旅行", "旅行"),
    ("出差", "出差"),
    ("工作", "工作"),
    ("项目", "工作"),
    ("记忆", "记忆写入"),
    ("闲聊", "闲聊"),
]


def _topic_of_text(text: str) -> str:
    """与前端 topics.ts 的 topicOfText 同规则：任何文本 → 规范主题。"""
    s = (text or "").lower()
    for pat, name in [
        (r"mcp|test|check", "测试数据"),
        (r"游泳|泳池|自由泳|蛙泳|蝶泳|仰泳|swim", "游泳记录"),
        (r"乒乓球|羽毛球|网球|篮球|足球|排球|台球|球类", "球类运动"),
        (r"5k|跑步|配速|半马|全马|\bpb\b|跑", "跑步记录"),
        (r"健身|骑行|瑜伽|增肌|力量训练", "健身记录"),
        (r"体重|身高|体脂|睡眠|心率|health", "身体数据"),
        (r"模型|model|大模型|大肥鱼|deepseek|minimax", "模型与配置"),
        (r"游戏|遗器|太空封印|崩铁|星穹|原神|绝区零|抽卡|角色|技能|副本|深渊|配队", "游戏"),
        (r"饮食|米饭|咖啡|早餐|午餐|晚餐|口味|吃|食物", "饮食偏好"),
        (r"宠物|猫|狗|鱼|豆豆|大肥鱼", "宠物"),
        (r"旅行|旅游|云南|大理|丽江|景点", "旅行"),
        (r"出差|成都|会议", "出差"),
        (r"工作|项目|开发|实现|anchorline|lorekeeper", "工作"),
        (r"记住|记忆|存下|保存|归档", "记忆写入"),
        (r"你好|hi|hello|在吗|闲聊", "闲聊"),
    ]:
        if re.search(pat, s):
            return name
    return "其他"


def _canonical_topic(topic: str) -> str:
    """把模型生成或历史遗留的 topic 归一到统一词表（与前端 topics.ts 对齐）。"""
    t = (topic or "").strip()
    if not t:
        return "其他"
    for kw, name in TOPIC_CANON:
        if t.startswith(kw) or kw in t:
            return name
    return _topic_of_text(t)


def _gen_topic_bg(sid: str, text: str, model: str) -> None:
    """后台生成/更新会话主题（用最近几轮对话；不占用响应时间）。"""
    if not sid:
        return
    from sqlalchemy import select

    from anchorline.db import session_factory
    from anchorline.models import Message as MsgModel

    db = session_factory()()
    try:
        row = db.get(ChatSession, sid)
        if row is None:
            return
        recent = list(db.scalars(select(MsgModel).where(MsgModel.session_id == sid).order_by(MsgModel.id.desc()).limit(6)).all())
        recent.reverse()
        convo = "\n".join(f"{m.role}: {m.content[:300]}" for m in recent) or text
        topic = _gen_topic(convo[:900], model)
        if topic:
            new_topic = _canonical_topic(topic)
            if new_topic != row.topic:
                row.topic = new_topic
                db.commit()
    except Exception:
        db.rollback()
        log.exception("topic generation failed")
    finally:
        db.close()


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, background: BackgroundTasks, db: Session = Depends(get_db)) -> ChatResponse:
    # 先确定会话（trace 需要 session_id，页面切换后 trace 也能按会话找回）
    sid = _ensure_session(db, req.session_id)

    try:
        out = _run_agent(req.messages, db, req.max_steps, model=req.model, session_id=sid)
    except HTTPException:
        raise
    except Exception as exc:  # 模型/DB 抖动：转成 502，前端弹窗提示而不是整页崩
        log.exception("chat failed")
        raise HTTPException(status_code=502, detail=f"聊天服务暂时不可用（{type(exc).__name__}），请重试") from exc
    finals = [m for m in out["messages"] if m.get("role") == "assistant" and (m.get("content") or "").strip()]
    answer = finals[-1]["content"] if finals else ""

    # 会话消息落库（失败不影响本轮回答）；主题生成放后台，不阻塞响应
    _persist_turn(db, sid, req.messages, answer, req.model)
    last_user_text = next((str(m.get("content") or "") for m in reversed(req.messages) if m.get("role") == "user"), "")
    background.add_task(_gen_topic_bg, sid or "", last_user_text, req.model)

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
            "recalls": out.get("recalls") or [],
            "intent": out.get("intent", "current"),
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
    recalls: str | None = None
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
        recalls=r.recalls,
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
    """删除会话、消息与 trace（记忆事实不受影响）。"""
    if db.get(ChatSession, session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    db.execute(delete(Message).where(Message.session_id == session_id))
    db.execute(delete(Trace).where(Trace.session_id == session_id))
    db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    db.commit()
    return {"deleted": session_id}


@app.post("/chat/stream")
def chat_stream(
    req: ChatRequest, background: BackgroundTasks, db: Session = Depends(get_db)
) -> StreamingResponse:
    """SSE：tool 事件 → token 事件（逐块推送最终答案，前端打字机）→ final；出错推 error 事件。"""

    def _gen():
        sid = _ensure_session(db, req.session_id)
        try:
            out = _run_agent(req.messages, db, req.max_steps, model=req.model, session_id=sid)
            for tc in _extract_tool_calls(out):
                yield "event: tool\ndata: " + json.dumps(tc, ensure_ascii=False) + "\n\n"
            finals = [m for m in out["messages"] if m.get("role") == "assistant" and (m.get("content") or "").strip()]
            answer = finals[-1]["content"] if finals else ""
            mode = (os.getenv("STREAM_MODE") or "chunk").strip().lower()
            if mode == "real":
                # 真流式：agent 完成后用完整对话（去掉最终回答）让模型逐 token 重新生成。
                # 代价：多一次模型调用；收益：真 token 流（首 token 延迟、逐字效果）。
                history = list(out["messages"])
                if history and history[-1].get("role") == "assistant":
                    history = history[:-1]
                client = chat_client(req.model)
                parts: list[str] = []
                for piece in client.stream(history, temperature=1.0, max_tokens=2048):
                    parts.append(piece)
                    yield "event: token\ndata: " + json.dumps({"text": piece}, ensure_ascii=False) + "\n\n"
                if parts:
                    answer = "".join(parts)
            else:
                # 伪流式（默认）：答案已生成后按小块推送，不额外调用模型
                for i in range(0, len(answer), 4):
                    chunk = answer[i:i + 4]
                    yield "event: token\ndata: " + json.dumps({"text": chunk}, ensure_ascii=False) + "\n\n"
            # 落库（与 /chat 同源）：会话消息 + 后台主题
            _persist_turn(db, sid, req.messages, answer, req.model)
            last_user_text = next(
                (str(m.get("content") or "") for m in reversed(req.messages) if m.get("role") == "user"), ""
            )
            background.add_task(_gen_topic_bg, sid or "", last_user_text, req.model)
            final_payload = {
                "answer": answer,
                "stop_reason": out.get("stop_reason", ""),
                "steps": out["steps"],
                "trace_id": out.get("trace_id"),
                "session_id": sid,
                "tool_calls": _extract_tool_calls(out),
                "meta": {
                    "model": req.model,
                    "duration_ms": out.get("duration_ms"),
                    "total_tokens": out.get("total_tokens"),
                    "tool_errors": out.get("tool_errors", 0),
                    "run_id": str(out.get("trace_id") or ""),
                    "intent": out.get("intent", "current"),
                },
            }
            yield "event: final\ndata: " + json.dumps(final_payload, ensure_ascii=False) + "\n\n"
        except Exception as exc:
            log.exception("chat stream failed")
            yield "event: error\ndata: " + json.dumps({"detail": f"{type(exc).__name__}: 生成失败"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream", background=background)


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
                    "content": "你是会话主题分类器。用 2-4 个汉字概括这段对话的主题（如：跑步、游泳、乒乓球、饮食、工作、模型与配置、宠物）。如果对话主体是大模型/DeepSeek 相关，输出「模型与配置」。只输出主题词，不要标点、不要解释。",
                },
                {"role": "user", "content": str(text)[:400]},
            ],
            temperature=0.0,
            max_tokens=512,  # reasoning 模型要给足思考 token（16 会被思考耗尽、content 为空）
        )
        topic = (out or "").strip().replace("\n", "").strip("。.，,：:")[:16]
        if topic:
            return topic
        # 兜底：模型空答案时用关键词规则，避免 topic 永远为 None
        low = str(text).lower()
        for kw, label in [
            ("跑", "跑步"), ("游泳", "游泳"), ("乒乓", "乒乓球"), ("网球", "球类运动"),
            ("篮球", "球类运动"), ("足球", "球类运动"), ("吃", "饮食"), ("工作", "工作"),
        ]:
            if kw in low:
                return label
        return str(text).strip()[:6] or "其他"
    except Exception:
        log.exception("topic generation failed")
        return ""


@app.delete("/memory/facts/{fact_id}")
def delete_fact(fact_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """物理删除一条记忆（用于控制存储量；其他事实不受影响）。"""
    fact = db.get(Fact, fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="fact not found")
    # 解除其它事实对它的 supersedes 引用，避免自引用外键阻止删除
    db.execute(update(Fact).where(Fact.supersedes_id == fact_id).values(supersedes_id=None))
    db.delete(fact)
    db.commit()
    try:
        from anchorline.retrieval import facts_index

        facts_index.delete_fact(fact_id)
    except Exception:
        log.warning("fact index delete failed", exc_info=True)
    return {"deleted": fact_id}


@app.delete("/memory/facts")
def purge_stale_facts(db: Session = Depends(get_db)) -> dict[str, int]:
    """批量清理已失效事实（控制存储量，保留当前值）。"""
    rows = list(db.scalars(select(Fact).where(Fact.valid_to.isnot(None))))
    ids = [f.id for f in rows]
    if ids:
        # 先解除自引用，再删除
        db.execute(update(Fact).where(Fact.supersedes_id.in_(ids)).values(supersedes_id=None))
        db.execute(delete(Fact).where(Fact.id.in_(ids)))
        db.commit()
    return {"deleted": len(ids)}


class ConflictEntity(BaseModel):
    entity_id: str
    facts: list[dict[str, Any]]


class ReviewDecisionIn(BaseModel):
    entity_id: str
    attribute: str | None = None
    kept_fact_id: str
    invalidated_fact_ids: list[str] = []
    reason: str | None = None


class ReviewDecisionOut(BaseModel):
    id: str
    entity_id: str
    attribute: str | None
    kept_fact_id: str
    invalidated_fact_ids: list[str]
    reason: str | None
    operator: str
    created_at: datetime


def _decision_out(d: ReviewDecision) -> ReviewDecisionOut:
    try:
        invalidated = json.loads(d.invalidated_fact_ids or "[]")
    except json.JSONDecodeError:
        invalidated = []
    return ReviewDecisionOut(
        id=d.id,
        entity_id=d.entity_id,
        attribute=d.attribute,
        kept_fact_id=d.kept_fact_id,
        invalidated_fact_ids=invalidated,
        reason=d.reason,
        operator=d.operator,
        created_at=d.created_at,
    )


@app.post("/review/decisions", response_model=ReviewDecisionOut)
def create_review_decision(body: ReviewDecisionIn, db: Session = Depends(get_db)) -> ReviewDecisionOut:
    """裁决：保留一条、其余标记失效，并记录金标（可追溯）。"""
    kept = db.get(Fact, body.kept_fact_id)
    if kept is None:
        raise HTTPException(status_code=404, detail="kept fact not found")
    now = datetime.now(timezone.utc)
    invalidated: list[str] = []
    for fid in body.invalidated_fact_ids:
        if fid == kept.id:
            continue
        f = db.get(Fact, fid)
        if f is not None and f.valid_to is None:
            f.valid_to = now
            invalidated.append(f.id)
    decision = ReviewDecision(
        entity_id=body.entity_id,
        attribute=body.attribute or kept.attribute,
        kept_fact_id=kept.id,
        invalidated_fact_ids=json.dumps(invalidated, ensure_ascii=False),
        reason=body.reason,
        operator="human",
    )
    db.add(decision)
    db.commit()
    for fid in invalidated:
        try:
            from anchorline.retrieval import facts_index

            facts_index.delete_fact(fid)
        except Exception:
            log.warning("fact index delete failed", exc_info=True)
    return _decision_out(decision)


@app.get("/review/decisions", response_model=list[ReviewDecisionOut])
def list_review_decisions(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[ReviewDecisionOut]:
    rows = list(db.scalars(select(ReviewDecision).order_by(ReviewDecision.created_at.desc()).limit(limit)))
    return [_decision_out(d) for d in rows]


@app.get("/review/conflicts", response_model=list[ConflictEntity])
def review_conflicts(db: Session = Depends(get_db)) -> list[ConflictEntity]:
    """审核队列：同一实体下「属性关键词重叠」的多个当前值（疑似冲突），供人工裁决。"""
    rows = list(
        db.scalars(select(Fact).where(Fact.valid_to.is_(None)).order_by(Fact.entity_id, Fact.attribute))
    )
    by_entity: dict[str, list[Fact]] = {}
    for f in rows:
        by_entity.setdefault(f.entity_id, []).append(f)
    out: list[ConflictEntity] = []
    for entity, facts in by_entity.items():
        clusters: list[list[Fact]] = []
        for f in facts:
            toks = _attr_tokens(f.attribute)
            placed = False
            for c in clusters:
                if any(toks & _attr_tokens(x.attribute) for x in c):
                    c.append(f)
                    placed = True
                    break
            if not placed:
                clusters.append([f])
        for c in clusters:
            if len(c) >= 2:
                out.append(
                    ConflictEntity(
                        entity_id=entity,
                        facts=[
                            {
                                "id": f.id,
                                "attribute": f.attribute,
                                "value": f.value,
                                "valid_from": f.valid_from.isoformat(),
                                "confidence": f.confidence,
                            }
                            for f in c
                        ],
                    )
                )
    return out


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
        try:
            from anchorline.retrieval import facts_index

            facts_index.delete_fact(fact.id)
        except Exception:
            log.warning("fact index delete failed", exc_info=True)
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


@app.get("/eval/lorekeeper", response_model=dict)
def eval_lorekeeper() -> dict:
    """LoreKeeper 数据集桥接实验汇总（chunk 级 + 页面级重排）。"""
    base = os.path.join(EVAL_DIR, "lorekeeper_bridge.json")
    page = os.path.join(EVAL_DIR, "lorekeeper_bridge_page.json")
    if not os.path.exists(base):
        raise HTTPException(status_code=404, detail="lorekeeper bridge result not found")
    with open(base, encoding="utf-8") as f:
        chunk = json.load(f)
    out = {"n": chunk.get("n"), "k": chunk.get("k"), "chunk": chunk.get("summary"), "page": None}
    if os.path.exists(page):
        with open(page, encoding="utf-8") as f:
            page_data = json.load(f)
        out["page"] = {
            "n": page_data.get("n"),
            "k": page_data.get("k"),
            "summary": page_data.get("summary"),
        }
    return out


@app.get("/eval/review-summary", response_model=dict)
def eval_review_summary(db: Session = Depends(get_db)) -> dict:
    """审核裁决金标汇总（供评测页展示；裁决记录本身在 /review/decisions）。"""
    rows = list(db.scalars(select(ReviewDecision).order_by(ReviewDecision.created_at.desc()).limit(100)))
    invalidated_total = 0
    for r in rows:
        try:
            invalidated_total += len(json.loads(r.invalidated_fact_ids or "[]"))
        except json.JSONDecodeError:
            pass
    return {
        "n": len(rows),
        "invalidated_total": invalidated_total,
        "recent": [
            {
                "entity_id": r.entity_id,
                "kept_fact_id": r.kept_fact_id,
                "reason": r.reason or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows[:10]
        ],
    }


def _arm_accuracy(data: dict, key: str | None) -> float | None:
    """优先读顶层字段；B 臂没有顶层 accuracy，用 per_question 均值。"""
    if key and isinstance(data.get(key), (int, float)):
        return float(data[key])
    means = [r.get("mean") for r in (data.get("per_question") or []) if isinstance(r.get("mean"), (int, float))]
    return sum(means) / len(means) if means else None


@app.get("/eval/summary", response_model=list[EvalArmOut])
def eval_summary() -> list[EvalArmOut]:
    """把 data/eval 下的结果汇总成臂级表；文件缺失/损坏只跳过，不抛 500。"""
    out: list[EvalArmOut] = []
    for fname, arm, key, note in [
        ("b_arm_154_run3.json", "B（官方基线）", None, "154 题，run3（当前口径）"),
        ("d_arm_154_run3.json", "D（完整轨迹+L0）", "d_accuracy", "154 题，run3（当前口径）"),
        ("c1_arm_154.json", "C1（完整轨迹×官方切片）", None, "154 题，2×2 因子"),
        ("c2_arm_154.json", "C2（a11y-only+L0）", "c2_accuracy", "154 题，2×2 因子"),
        ("d_arm_154_neighbor.json", "D（state+邻居）", "d_accuracy", "154 题，检索粒度对照"),
    ]:
        d = _load_eval(fname)
        if not d:
            continue
        acc = _arm_accuracy(d, key)
        if acc is None:
            continue
        n = int(
            d.get("n_questions")
            or (d.get("config") or {}).get("n_questions")
            or len(d.get("per_question", []))
        )
        out.append(EvalArmOut(arm=arm, accuracy=acc, n=n, source=fname, note=note))

    for fname, note in [
        ("arm_168_run3.json", "154 + 14 judge，run3"),
        ("arm_168_run2.json", "154 + 14 judge，run2"),
    ]:
        a168 = _load_eval(fname)
        if not a168:
            continue
        n = int(a168.get("n_common", 0))
        out.append(EvalArmOut(arm=f"B（168，{fname[-10:-5]}）", accuracy=float(a168["b_accuracy"]), n=n, source=fname, note=note))
        out.append(EvalArmOut(arm=f"D（168，{fname[-10:-5]}）", accuracy=float(a168["d_accuracy"]), n=n, source=fname, note=note))
    return out
