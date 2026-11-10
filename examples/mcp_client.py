# -*- coding: utf-8 -*-
"""MCP 客户端示例：以 stdio 连到 `anchorline.mcp_server`，调 memory_search / memory_write。

用法（在仓库根）：
    .venv\\Scripts\\python.exe examples\\mcp_client.py

依赖：mcp（与 server 同一依赖）。注意 server 用同一数据库（.env）。
"""
from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable


async def main() -> int:
    params = StdioServerParameters(
        command=PY,
        args=["-m", "anchorline.mcp_server"],
        env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])

            w = await session.call_tool(
                "memory_write",
                {"entity_id": "user:mcp_example", "attribute": "demo", "value": "hello"},
            )
            print("write:", w.content)

            s = await session.call_tool("memory_search", {"query": "demo", "budget_tokens": 500})
            print("search:", s.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
