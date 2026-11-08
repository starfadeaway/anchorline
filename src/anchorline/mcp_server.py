# -*- coding: utf-8 -*-
"""thin MCP server：memory_search / memory_write / memory_forget。

- 与内部聊天/评测路径**同源**（都调用 `anchorline.tools.build_tools`）；
- schema 由 FastMCP 依据函数签名生成；错误在工具内捕获并返回文本；
- stdio transport：`python -m anchorline.mcp_server`。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from mcp.server.fastmcp import FastMCP

from anchorline.db import session_factory
from anchorline.memory.store import FactStore
from anchorline.tools import build_tools

mcp = FastMCP("anchorline-memory")


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
        return f"memory_search failed: {exc}"


@mcp.tool()
def memory_write(entity_id: str, attribute: str, value: str, valid_from: str | None = None) -> str:
    """Write a fact. Old value is superseded (valid_to), never physically deleted."""
    try:
        with _tools() as t:
            return t["memory_write"](
                entity_id=entity_id, attribute=attribute, value=value, valid_from=valid_from
            ).content
    except Exception as exc:
        return f"memory_write failed: {exc}"


@mcp.tool()
def memory_forget(entity_id: str, attribute: str, at: str | None = None) -> str:
    """Mark the current fact invalid (no physical delete)."""
    try:
        with _tools() as t:
            return t["memory_forget"](entity_id=entity_id, attribute=attribute, at=at).content
    except Exception as exc:
        return f"memory_forget failed: {exc}"


if __name__ == "__main__":
    mcp.run()
