# -*- coding: utf-8 -*-
"""真实 tool-calling 冒烟：LangGraph agent → DeepSeek function calling → memory 工具。

用法：.venv\\Scripts\\python.exe scripts\\smoke_chat_agent.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.db import session_factory  # noqa: E402
from anchorline.graph.chat import Bounds, build_chat_graph, initial_state  # noqa: E402
from anchorline.llm import reader_client  # noqa: E402
from anchorline.memory.store import FactStore  # noqa: E402
from anchorline.tools import TOOL_SCHEMAS  # noqa: E402


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印将写入的事实，不写库、不调模型")
    args = ap.parse_args()
    if args.dry_run:
        print("dry-run: 将写 entity_id='user:smoke', attribute='5K best time', value='25:50'（未执行）")
        return 0
    db = session_factory()()
    store = FactStore(db)
    reader = reader_client()

    def model_fn(msgs):
        return reader.complete_with_tools(msgs, TOOL_SCHEMAS, max_tokens=2048)

    graph = build_chat_graph(store, model_fn, Bounds(max_steps=6, max_tokens=24000, wall_time_s=180.0))
    messages = [{
        "role": "user",
        "content": (
            "请用记忆工具完成两步：1) 调 memory_write 存一条事实 "
            "entity_id='user:smoke', attribute='5K best time', value='25:50', valid_from='2023-05-30'；"
            "2) 调 memory_search 查询 '5K best time'，然后告诉我检索结果。"
        ),
    }]
    out = graph.invoke(initial_state(messages), {"configurable": {"thread_id": "smoke-chat"}})
    db.commit()
    print("stop_reason:", out.get("stop_reason"), "| steps:", out["steps"])
    for m in out["messages"]:
        role = m.get("role")
        content = (m.get("content") or "").replace("\n", " ")[:300]
        calls = m.get("tool_calls") or []
        print(f"[{role}] {content}")
        for tc in calls:
            print(f"    tool_call: {tc.get('name')} args={str(tc.get('arguments'))[:200]}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
