# -*- coding: utf-8 -*-
"""全量重建 facts 向量索引（写入时已同步 upsert；此脚本用于初始化/修复）。

用法：.venv\\Scripts\\python.exe scripts\\rebuild_facts_index.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.db import session_factory  # noqa: E402
from anchorline.retrieval.facts_index import rebuild_all  # noqa: E402


def main() -> int:
    with session_factory()() as db:
        n = rebuild_all(db)
        print(f"rebuilt facts_index: {n} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
