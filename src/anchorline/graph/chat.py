# -*- coding: utf-8 -*-
"""LangGraph 聊天主循环（bounded agent loop）。

- 使用 StateGraph + 普通边 + 条件边 + `session_state` checkpointer（InMemorySaver）；
- **bounded**：max_steps / max_tokens / wall_time / no-progress 四道闸；
- 只有「下一步取决于模型判断」的聊天才走这个 loop；摄入 / 压缩 / 评测走确定性 workflow（见 workflows.py）。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph

from anchorline.memory.store import FactStore
from anchorline.tools import ToolResult, build_tools


class ChatState(TypedDict):
    messages: list[dict]
    steps: int
    tokens: int
    stop_reason: str
    started_at: float
    last_signature: str
    repeat_count: int
    # 召回明细（memory_search 的 BM25/向量/RRF/rerank 分数），供 trace 展示
    recalls: list[dict]


@dataclass
class Bounds:
    max_steps: int = 8
    max_tokens: int = 8000
    wall_time_s: float = 120.0
    max_repeats: int = 2


def _estimate_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += len(str(m.get("content", ""))) // 4
        for tc in m.get("tool_calls") or []:
            total += len(json.dumps(tc, ensure_ascii=False)) // 4
    return total


def build_chat_graph(
    store: FactStore,
    model_fn: Callable[[list[dict]], dict],
    bounds: Bounds | None = None,
    session_id: str | None = None,
):
    """model_fn(messages) -> {"content": str, "tool_calls": [{"id","name","arguments"}]}"""
    bounds = bounds or Bounds()
    tools = build_tools(store, session_id)

    def agent(state: ChatState) -> dict:
        reply = model_fn(state["messages"])
        msg = {"role": "assistant", "content": reply.get("content") or ""}
        if reply.get("tool_calls"):
            # 回传给模型时必须用 OpenAI 标准格式：{id, type:"function", function:{name, arguments}}
            msg["tool_calls"] = [
                {
                    "id": tc.get("id") or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc.get("name") or tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("arguments") or tc.get("function", {}).get("arguments") or "{}",
                    },
                }
                for i, tc in enumerate(reply["tool_calls"])
            ]
        messages = [*state["messages"], msg]
        return {
            "messages": messages,
            "steps": state["steps"] + 1,
            "tokens": _estimate_tokens(messages),
        }

    def tool_node(state: ChatState) -> dict:
        last = state["messages"][-1]
        out = list(state["messages"])
        recalls = list(state.get("recalls") or [])
        sig_parts = []
        for tc in last.get("tool_calls") or []:
            name = tc.get("name") or tc.get("function", {}).get("name", "")
            args = tc.get("arguments") or tc.get("function", {}).get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            sig_parts.append(f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}")
            fn = tools.get(name)
            if fn is None:
                result = ToolResult(ok=False, content=f"unknown tool: {name}", meta={})
            else:
                try:
                    result = fn(**args)
                except Exception as exc:  # 工具异常不外抛，交给模型看错误
                    result = ToolResult(ok=False, content=f"tool error: {exc}", meta={})
            # memory_search 会带回收召回明细（分数），累计进 state 供 trace
            if isinstance(result.meta.get("recalls"), list):
                recalls.extend(result.meta["recalls"])
            out.append({
                "role": "tool",
                "tool_call_id": tc.get("id") or "",
                "name": name,
                "content": result.content,
            })
        signature = "|".join(sig_parts)
        repeat = state["repeat_count"] + 1 if signature and signature == state["last_signature"] else 0
        return {
            "messages": out,
            "last_signature": signature,
            "repeat_count": repeat,
            "tokens": _estimate_tokens(out),
            "recalls": recalls,
        }

    def route(state: ChatState) -> str:
        last = state["messages"][-1]
        if state["steps"] >= bounds.max_steps:
            return "stop_max_steps"
        if state["tokens"] > bounds.max_tokens:
            return "stop_max_tokens"
        if time.monotonic() - state["started_at"] > bounds.wall_time_s:
            return "stop_wall_time"
        if state["repeat_count"] >= bounds.max_repeats:
            return "stop_no_progress"
        if not last.get("tool_calls"):
            return "done"
        return "tools"

    def stop(reason: str):
        def _node(state: ChatState) -> dict:
            return {"stop_reason": reason}
        return _node

    g = StateGraph(ChatState)
    g.add_node("agent", agent)
    g.add_node("tools", tool_node)
    g.add_node("stop_max_steps", stop("max_steps"))
    g.add_node("stop_max_tokens", stop("max_tokens"))
    g.add_node("stop_wall_time", stop("wall_time"))
    g.add_node("stop_no_progress", stop("no_progress"))
    g.add_node("done", stop("done"))
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", route, {
        "tools": "tools",
        "done": "done",
        "stop_max_steps": "stop_max_steps",
        "stop_max_tokens": "stop_max_tokens",
        "stop_wall_time": "stop_wall_time",
        "stop_no_progress": "stop_no_progress",
    })
    g.add_edge("tools", "agent")
    for n in ("done", "stop_max_steps", "stop_max_tokens", "stop_wall_time", "stop_no_progress"):
        g.add_edge(n, END)
    # 不挂 checkpointer：每次请求新建 graph，无恢复需求（避免 InMemorySaver 累积，P2-6）
    return g.compile()


def initial_state(messages: list[dict]) -> ChatState:
    return {
        "messages": messages,
        "steps": 0,
        "tokens": _estimate_tokens(messages),
        "stop_reason": "",
        "started_at": time.monotonic(),
        "last_signature": "",
        "repeat_count": 0,
        "recalls": [],
    }
