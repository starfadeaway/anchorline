# -*- coding: utf-8 -*-
"""MCP 集成测试：以 stdio 子进程启动 anchorline.mcp_server，真实调用三工具。

依赖：本机 MySQL 运行 + 仓库根 `.env` 已配置；否则跳过。
验证点：
  - server 能 list_tools 出三个工具；
  - memory_write → memory_search → memory_forget 往返可用；
  - 返回文本与内部 `build_tools` 的语义一致（写入后可检索、forget 后标记失效）。
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")


def _mysql_available() -> bool:
    """探测 MySQL 端口；服务停止时让集成测试 skip 而不是 fail。"""
    try:
        with socket.create_connection(("127.0.0.1", 3306), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(not os.path.exists(ENV_FILE), reason="需要 .env（MySQL 连接）"),
    pytest.mark.skipif(not _mysql_available(), reason="MySQL 未运行（3306 不可达）"),
]


def _params():
    from mcp import StdioServerParameters

    env = {**os.environ}
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    env["PYTHONIOENCODING"] = "utf-8"
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "anchorline.mcp_server"],
        env=env,
        cwd=ROOT,
    )


@pytest.mark.asyncio
async def test_mcp_tools_roundtrip():
    from mcp import ClientSession, StdioServerParameters  # noqa: F401
    from mcp.client.stdio import stdio_client

    # 唯一 attribute，保证测试可重复跑（上次 forget 会把旧 fact 置为失效）
    import uuid
    attr = f"mcp check {uuid.uuid4().hex[:8]}"

    async with stdio_client(_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"memory_search", "memory_write", "memory_forget"} <= names, names

            w = await session.call_tool(
                "memory_write",
                {"entity_id": "user:mcp", "attribute": attr, "value": "ok-2023", "valid_from": "2023-01-01"},
            )
            text = "".join(getattr(c, "text", "") for c in (w.content or []))
            assert "fact_id" in text, text
            fact_id = json.loads(text)["fact_id"]

            s = await session.call_tool("memory_search", {"query": attr, "budget_tokens": 500})
            stext = "".join(getattr(c, "text", "") for c in (s.content or []))
            assert f"user:mcp.{attr} = ok-2023" in stext, stext

            f = await session.call_tool("memory_forget", {"entity_id": "user:mcp", "attribute": attr})
            ftext = "".join(getattr(c, "text", "") for c in (f.content or []))
            assert "marked invalid" in ftext, ftext
            assert fact_id in ftext, ftext
