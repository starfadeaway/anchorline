# -*- coding: utf-8 -*-
"""一键 demo：演示 Anchorline 的记忆写入 → 更新（自动失效）→ 混合检索（含召回明细）。

前置：API 已启动（默认 http://127.0.0.1:8000）。
用法：.venv\\Scripts\\python.exe scripts\\demo.py
"""
from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"
ENTITY = "user:demo"


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def facts_of(entity: str) -> list[dict]:
    rows = call("GET", "/memory/facts?limit=200")
    return [f for f in rows if f["entity_id"] == entity]


def main() -> int:
    print("== Anchorline demo ==")
    print("[1] 写入记忆：5K 最好成绩 25:50（2023-05-30）")
    call("POST", "/memory/write", {"entity_id": ENTITY, "attribute": "5k_pb", "value": "25:50（2023-05-30）"})

    print("[2] 更新成绩：24:30 —— 旧值应自动标记失效（不删除）")
    call("POST", "/memory/write", {"entity_id": ENTITY, "attribute": "5k_pb", "value": "24:30"})
    rows = facts_of(ENTITY)
    for f in rows:
        print(f"    - {f['attribute']} = {f['value']}  ->", "已失效" if f["valid_to"] else "当前")

    print("[3] 混合检索：query='跑步 成绩'（BM25 + 向量 + RRF + rerank）")
    res = call("POST", "/memory/search", {"query": "跑步 成绩", "limit": 3})
    for line in res["text"].split("\n\n"):
        if line.strip():
            print("    " + line.replace("\n", " | "))

    print("[4] 容量视图")
    cap = call("GET", "/memory/capacity")
    print(f"    当前值 {cap['total_current']} 条 / 每实体上限 {cap['limit']} 条")

    print("[5] 清理 demo 数据")
    for f in facts_of(ENTITY):
        call("DELETE", "/memory/facts/" + f["id"])
    print("    已清理")
    print("== demo 结束 ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
