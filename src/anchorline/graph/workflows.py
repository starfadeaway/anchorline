# -*- coding: utf-8 -*-
"""确定性 workflow：摄入 / L0 去重 / L1 观测摘要 / trace 落库。

v0.8 分工：**确定性步骤走 workflow**（不是 LLM 循环）；只有聊天才走 `graph/chat.py` 的 agent loop。
两者都用 LangGraph StateGraph 表达。
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
    raw_chars: int
    l0_text: str
    l0_lines: int
    l1_text: str
    events: int
    l0_ratio: float
    trace_id: int | None


def build_ingest_graph(db: Session):
    deduper = L0Deduper()

    def l0(state: IngestState) -> dict:
        deduper._seen.clear()
        deduper.stats.raw_lines = 0
        deduper.stats.novel_lines = 0
        deduper.stats.raw_chars = 0
        deduper.stats.novel_chars = 0
        text = deduper.feed_states(state["states"])
        return {
            "l0_text": text,
            "l0_lines": deduper.stats.novel_lines,
            "l0_ratio": deduper.stats.compression,
        }

    def l1(state: IngestState) -> dict:
        lines = [line for line in state["l0_text"].split("\n") if line.strip()]
        # L0 输出是行文本；L1 需要原始 state 结构才保留 url/action/thought，
        # 因此这里把 L0 行按 state 分块反向解析为事件（每块的行前缀含 "#idx | @url | action=.. | thought=.."）
        events = []
        for line in lines:
            if line.startswith("#"):
                events.append(line)
        return {"l1_text": "\n".join(events), "events": len(events)}

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
    """确定性摄入一条轨迹：states -> L0 -> L1 -> trace。"""
    states = [
        (s.get("accessibility_tree") or "")
        for s in (traj.get("states") or [])
        if isinstance(s, dict)
    ]
    state: IngestState = {
        "traj_id": str(traj.get("id", "unknown")),
        "states": states,
        "raw_chars": sum(len(s) for s in states),
        "l0_text": "",
        "l0_lines": 0,
        "l1_text": "",
        "events": 0,
        "l0_ratio": 0.0,
        "trace_id": None,
    }
    out = build_ingest_graph(db).invoke(state)
    return out
