# -*- coding: utf-8 -*-
"""事实（facts）的向量索引：LanceDB 表 `facts_index`。

写入时同步 upsert（P0-2 决策 A）；失败不阻断写入，只记日志。
检索由 `hybrid.hybrid_search` 使用（BM25 + 向量 + RRF + rerank）。
"""
from __future__ import annotations

import logging
import re

from anchorline.config import Settings
from anchorline.llm import embedding_client
from anchorline.models import Fact
from anchorline.retrieval.store import open_lancedb

log = logging.getLogger("anchorline.retrieval.facts_index")

TABLE = "facts_index"


def topic_hint(f: Fact) -> str:
    """给事实加主题标签，提升中文检索命中（如 5k_pb → 跑步）。"""
    s = f"{f.entity_id} {f.attribute} {f.value}".lower()
    if re.search(r"游泳|泳池|自由泳|蛙泳|蝶泳|仰泳", s):
        return "游泳"
    if re.search(r"5k|跑步|配速|跑|半马|全马", s):
        return "跑步"
    if re.search(r"乒乓球|羽毛球|网球|篮球|足球|排球", s):
        return "球类运动"
    if re.search(r"体重|身高|体脂|睡眠|心率", s):
        return "身体数据"
    if re.search(r"模型|model|deepseek|minimax", s):
        return "模型"
    if re.search(r"mcp|test|check", s):
        return "测试"
    return ""


def fact_text(f: Fact) -> str:
    base = f"{f.entity_id} {f.attribute} {f.value}"
    hint = topic_hint(f)
    return f"{base}（主题：{hint}）" if hint else base


def upsert_fact(fact: Fact, settings: Settings | None = None) -> bool:
    """为一条事实生成向量并写入索引（同步；失败返回 False，不影响写入）。"""
    try:
        db = open_lancedb()
        vec = embedding_client(settings).embed([fact_text(fact)])[0]
        row = {
            "id": fact.id,
            "entity_id": fact.entity_id,
            "attribute": fact.attribute,
            "value": fact.value,
            "text": fact_text(fact),
            "vector": vec,
        }
        if TABLE not in db.table_names():
            db.create_table(TABLE, data=[row])
            return True
        tbl = db.open_table(TABLE)
        try:
            tbl.delete(f"id = '{fact.id}'")
        except Exception:
            pass  # 新事实没有旧行
        tbl.add([row])
        return True
    except Exception:
        log.warning("failed to index fact %s", fact.id, exc_info=True)
        return False


def delete_fact(fact_id: str) -> bool:
    try:
        db = open_lancedb()
        if TABLE not in db.table_names():
            return True
        db.open_table(TABLE).delete(f"id = '{fact_id}'")
        return True
    except Exception:
        log.warning("failed to delete fact index %s", fact_id, exc_info=True)
        return False


def rebuild_all(db_session, settings: Settings | None = None) -> int:
    """全量重建索引（脚本/运维用）。返回重建条数。"""
    from sqlalchemy import select

    from anchorline.models import Fact

    rows = list(db_session.scalars(select(Fact)))
    if not rows:
        return 0
    emb = embedding_client(settings)
    vectors = emb.embed([fact_text(f) for f in rows])
    payload = [
        {
            "id": f.id,
            "entity_id": f.entity_id,
            "attribute": f.attribute,
            "value": f.value,
            "text": fact_text(f),
            "vector": v,
        }
        for f, v in zip(rows, vectors)
    ]
    open_lancedb().create_table(TABLE, data=payload, mode="overwrite")
    return len(payload)


def search_vector(query: str, k: int = 20, settings: Settings | None = None) -> list[tuple[str, float]]:
    """向量检索：返回 [(fact_id, score)]，score 越大越相关（1 - distance）。"""
    try:
        db = open_lancedb()
        if TABLE not in db.table_names():
            return []
        vec = embedding_client(settings).embed([query])[0]
        rows = db.open_table(TABLE).search(vec).limit(k).to_list()
        return [(r["id"], 1.0 - float(r.get("_distance") or 0.0)) for r in rows]
    except Exception:
        log.warning("vector search failed", exc_info=True)
        return []
