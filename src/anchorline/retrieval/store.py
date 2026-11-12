# -*- coding: utf-8 -*-
"""LanceDB 连接与表访问（统一入口，避免各脚本重复写路径）。"""
from __future__ import annotations

from anchorline.paths import LANCEDB_DIR

DEFAULT_LANCEDB = LANCEDB_DIR


def open_lancedb(root: str | None = None):
    """连接本地 LanceDB（默认 `data/lancedb`）。

    注意：LanceDB 是可选依赖，只有建索引/评测脚本需要；API 主路径不依赖它。
    """
    import lancedb

    return lancedb.connect(root or DEFAULT_LANCEDB)


def open_table(name: str, root: str | None = None):
    """打开一个已有的表（不存在会抛异常）。"""
    return open_lancedb(root).open_table(name)
