# -*- coding: utf-8 -*-
"""确定性 workflow：摄入 / L0 去重 / L1 观测摘要 / trace 落库。

v0.8 分工：**确定性步骤走 workflow**（不是 LLM 循环）；只有聊天才走 `graph/chat.py` 的 agent loop。
两者都用 LangGraph StateGraph 表达。

L0 与 L1 处理的是不同字段：
  - L0：states[*].accessibility_tree 的跨 state 行级去重（体积压缩）；
  - L1：states[*] 的 url / action / thought → 事件行（可读、可追溯）。
不要把 L1 反解成 L0 的行文本 —— 那是两件事。
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from anchorline.memory.l0 import L0Deduper
from anchorline.memory.l1 import events_to_text, summarize_states
from anchorline.models import Trace


class IngestState(TypedDict):
    traj_id: str
    states: list[str]
    states_meta: list[dict]
    raw_chars: int
    l0_text: str
    l0_lines: int
    l1_text: str
    events: int
    l0_ratio: float
    trace_id: int | None


def build_ingest_graph(db: Session):
    def l0(state: IngestState) -> dict:
        deduper = L0Deduper()
        text = deduper.feed_states(state["states"])
        return {
            "l0_text": text,
            "l0_lines": deduper.stats.novel_lines,
            "l0_ratio": deduper.stats.compression,
        }

    def l1(state: IngestState) -> dict:
        events = summarize_states(state["states_meta"])
        return {"l1_text": events_to_text(events), "events": len(events)}

    def persist(state: IngestState) -> dict:
        trace = Trace(
            session_id=state["traj_id"][:32],
            query=f"ingest:{state['traj_id']}",
            budget_tokens=0,
            used_tokens=len(state["l1_text"]) // 4,
            layers="L0>L1",
            injected_fact_ids=None,
        )
        db.add(trace)
        db.flush()
        return {"trace_id": trace.id}

    g = StateGraph(IngestState)
    g.add_node("l0", l0)
    g.add_node("l1", l1)
    g.add_node("persist", persist)
    g.set_entry_point("l0")
    g.add_edge("l0", "l1")
    g.add_edge("l1", "persist")
    g.add_edge("persist", END)
    return g.compile()


def ingest_trajectory(traj: dict, db: Session) -> IngestState:
    """确定性摄入一条轨迹：a11y → L0；state 元数据 → L1；最后 trace。"""
    states_meta = [s for s in (traj.get("states") or []) if isinstance(s, dict)]
    states = [(s.get("accessibility_tree") or "") for s in states_meta]
    state: IngestState = {
        "traj_id": str(traj.get("id", "unknown")),
        "states": states,
        "states_meta": states_meta,
        "raw_chars": sum(len(s) for s in states),
        "l0_text": "",
        "l0_lines": 0,
        "l1_text": "",
        "events": 0,
        "l0_ratio": 0.0,
        "trace_id": None,
    }
    return build_ingest_graph(db).invoke(state)
