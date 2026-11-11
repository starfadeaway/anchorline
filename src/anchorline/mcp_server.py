# -*- coding: utf-8 -*-
"""thin MCP server：memory_search / memory_write / memory_forget / kb_search。

- 与内部聊天/评测路径**同源**（都调用 `anchorline.tools.build_tools`）；
- schema 由 FastMCP 依据函数签名生成；错误在工具内捕获并返回文本；
- stdio transport：`python -m anchorline.mcp_server`。
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from mcp.server.mcpserver import MCPServer

from anchorline.db import session_factory
from anchorline.memory.store import FactStore
from anchorline.tools import build_tools

log = logging.getLogger("anchorline.mcp")

# mcp 2.x：FastMCP 已更名为 MCPServer（from mcp.server.mcpserver import MCPServer）
mcp = MCPServer("anchorline-memory")


@contextmanager
def _tools() -> Iterator[dict]:
    db = session_factory()()
    try:
        yield build_tools(FactStore(db))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@mcp.tool()
def memory_search(query: str, budget_tokens: int = 2000) -> str:
    """Search memory under a token budget. Returns matching facts with ids."""
    try:
        with _tools() as t:
            return t["memory_search"](query=query, budget_tokens=budget_tokens).content
    except Exception as exc:  # 错误以文本返回，不中断会话
        log.warning("memory_search failed: %s", exc)
        return "检索失败，请稍后重试（详情见服务端日志）"


@mcp.tool()
def memory_write(entity_id: str, attribute: str, value: str, valid_from: str | None = None) -> str:
    """Write a fact. Old value is superseded (valid_to), never physically deleted."""
    try:
        with _tools() as t:
            return t["memory_write"](
                entity_id=entity_id, attribute=attribute, value=value, valid_from=valid_from
            ).content
    except Exception as exc:
        log.warning("memory_write failed: %s", exc)
        return "写入失败，请稍后重试（详情见服务端日志）"


@mcp.tool()
def memory_forget(entity_id: str, attribute: str, at: str | None = None) -> str:
    """Mark the current fact invalid (no physical delete)."""
    try:
        with _tools() as t:
            return t["memory_forget"](entity_id=entity_id, attribute=attribute, at=at).content
    except Exception as exc:
        log.warning("memory_forget failed: %s", exc)
        return "删除失败，请稍后重试（详情见服务端日志）"


@mcp.tool()
def kb_search(query: str, game: str = "", top_k: int = 3) -> str:
    """Search the LoreKeeper game wiki (sr/ys/zzz). Use for factual game questions, not personal memories."""
    try:
        with _tools() as t:
            return t["kb_search"](query=query, game=game, top_k=top_k).content
    except Exception as exc:
        return f"kb_search failed: {exc}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
