# -*- coding: utf-8 -*-
"""LangGraph bounded chat loop 单测（fake model，不调外部 API）。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.graph.chat import Bounds, build_chat_graph, initial_state
from anchorline.memory.store import FactStore
from anchorline.models import Base, Fact


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _write_then_answer(messages):
    if not any(m.get("role") == "assistant" for m in messages):
        return {
            "content": "",
            "tool_calls": [{
                "id": "c1",
                "name": "memory_write",
                "arguments": {
                    "entity_id": "user:liu",
                    "attribute": "5K best time",
                    "value": "25:50",
                    "valid_from": "2023-05-30",
                },
            }],
        }
    return {"content": "noted", "tool_calls": []}


def test_loop_writes_fact_and_stops_with_done(db):
    store = FactStore(db)
    app = build_chat_graph(store, _write_then_answer, Bounds(max_steps=5))
    out = app.invoke(initial_state([{"role": "user", "content": "my 5K best is 25:50"}]), {"configurable": {"thread_id": "t1"}})
    db.commit()
    assert out["stop_reason"] == "done"
    assert out["steps"] == 2
    facts = db.query(Fact).all()
    assert len(facts) == 1
    assert facts[0].value == "25:50"
    # 语义变更：记忆的生效时间 = 记录/会话时间，不是对话里提到的事件日期
    assert facts[0].valid_from > datetime(2024, 1, 1)


def _always_search(messages):
    return {"content": "", "tool_calls": [{"id": "s", "name": "memory_search", "arguments": {"query": "x"}}]}


def test_max_steps_bound(db):
    app = build_chat_graph(FactStore(db), _always_search, Bounds(max_steps=2, max_repeats=99))
    out = app.invoke(initial_state([{"role": "user", "content": "hi"}]), {"configurable": {"thread_id": "t2"}})
    assert out["stop_reason"] == "max_steps"
    assert out["steps"] == 2


def test_no_progress_bound(db):
    # repeat_count 从第 2 次相同工具调用起算；max_repeats=2 在第 3 次工具调用后的 agent 轮触发
    app = build_chat_graph(FactStore(db), _always_search, Bounds(max_steps=10, max_repeats=2))
    out = app.invoke(initial_state([{"role": "user", "content": "hi"}]), {"configurable": {"thread_id": "t3"}})
    assert out["stop_reason"] == "no_progress"
    assert out["steps"] == 4


def test_unknown_tool_does_not_crash(db):
    def bad(messages):
        if not any(m.get("role") == "tool" for m in messages):
            return {"content": "", "tool_calls": [{"id": "b", "name": "nope", "arguments": {}}]}
        return {"content": "ok", "tool_calls": []}

    app = build_chat_graph(FactStore(db), bad, Bounds(max_steps=4))
    out = app.invoke(initial_state([{"role": "user", "content": "hi"}]), {"configurable": {"thread_id": "t4"}})
    assert out["stop_reason"] == "done"
    tool_msgs = [m for m in out["messages"] if m.get("role") == "tool"]
    assert tool_msgs and "unknown tool" in tool_msgs[0]["content"]
