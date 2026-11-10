# -*- coding: utf-8 -*-
"""清理开发测试留下的事实（mcp check / webtest / smoke 等），保留演示数据。

用法：.venv\\Scripts\\python.exe scripts\\clean_test_facts.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from sqlalchemy import delete, select  # noqa: E402

from anchorline.db import session_factory  # noqa: E402
from anchorline.models import Fact  # noqa: E402

# 测试/冒烟数据前缀（entity_id）
TEST_PREFIXES = ("user:mcp", "user:webtest", "user:http", "user:smoke", "user:probe")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不删除")
    args = ap.parse_args()

    with session_factory()() as db:
        rows = list(db.scalars(select(Fact)))
        targets = [f for f in rows if any(f.entity_id.startswith(p) for p in TEST_PREFIXES)]
        for f in targets[:20]:
            print(f"  {f.entity_id}.{f.attribute} = {f.value[:40]}")
        print(f"测试事实：{len(targets)} / 总计 {len(rows)}")
        if args.dry_run or not targets:
            return 0
        ids = [f.id for f in targets]
        db.execute(delete(Fact).where(Fact.id.in_(ids)))
        db.commit()
        print(f"已删除 {len(ids)} 条测试事实")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
