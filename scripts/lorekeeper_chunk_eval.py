# -*- coding: utf-8 -*-
"""chunk 级检索评测（用自动生成的 chunk gold）：纯向量 vs RRF vs RRF+rerank。

gold：`data/eval/lorekeeper_chunk_gold.json`（auto-generated：每个 gold 页面取与问题最相似的 chunk）。
指标：chunk 级 Recall@k（检索 top-k chunk 与 gold chunk id 的交集）。

用法：.venv\\Scripts\\python.exe scripts\\lorekeeper_chunk_eval.py --k 5
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import jieba  # noqa: E402
import lancedb  # noqa: E402
from rank_bm25 import BM25Plus  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.llm import EmbeddingClient, ReaderConfig, rerank_client  # noqa: E402

LK = os.environ.get("LOREKEEPER_DIR")  # U8：必须显式设置，不再硬编码他项目本机路径
LK_LANCE = os.path.join(LK, "data", "lance")
LK_EMBED = "BAAI/bge-m3"
GOLD = os.path.join(ROOT, "data", "eval", "lorekeeper_chunk_gold.json")

_cache: dict[str, dict] = {}


def load_game(game: str) -> dict:
    if game in _cache:
        return _cache[game]
    db = lancedb.connect(LK_LANCE)
    tbl = db.open_table(f"kb_{game}_baai-bge-m3_base")
    rows = tbl.to_arrow().select(["id", "page_title", "text"]).to_pylist()
    tokens = [[t for t in jieba.lcut(r.get("text") or "") if t.strip()] for r in rows]
    _cache[game] = {"tbl": tbl, "rows": rows, "bm25": BM25Plus(tokens), "id2row": {r["id"]: r for r in rows}}
    return _cache[game]


def vec_top(tbl, vec: list[float], k: int) -> list[dict]:
    return tbl.search(vec).select(["id", "page_title", "text"]).limit(k).to_list()


def rrf_top(game: str, question: str, vec: list[float], k: int) -> list[str]:
    data = load_game(game)
    rows, bm25 = data["rows"], data["bm25"]
    scores = bm25.get_scores([t for t in jieba.lcut(question) if t.strip()])
    bm_ids = [rows[i]["id"] for i in sorted(range(len(rows)), key=lambda i: -float(scores[i])) if scores[i] > 0][:30]
    vec_ids = [r["id"] for r in vec_top(data["tbl"], vec, 20)]
    rrf: dict[str, float] = {}
    for ids in (bm_ids, vec_ids):
        for rank, rid in enumerate(ids):
            rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (60 + rank + 1)
    return [rid for rid, _ in sorted(rrf.items(), key=lambda kv: -kv[1])][:k]


def rerank_top(game: str, question: str, vec: list[float], k: int) -> list[str]:
    data = load_game(game)
    cand_ids = rrf_top(game, question, vec, 20)
    cands = [data["id2row"][rid] for rid in cand_ids if rid in data["id2row"]]
    if not cands:
        return []
    try:
        scored = rerank_client().rerank(question, [c["text"][:2000] for c in cands], top_n=k)
        return [cands[i]["id"] for i, _ in scored if 0 <= i < len(cands)][:k]
    except Exception:
        return cand_ids[:k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--gold", default=GOLD)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "eval", "_drafts", "lorekeeper_chunk_eval.json"))
    args = ap.parse_args()

    gold = json.load(open(args.gold, encoding="utf-8"))["rows"]
    s = Settings()
    emb = EmbeddingClient(ReaderConfig(s.siliconflow_base_url, s.siliconflow_api_key, LK_EMBED))

    results = []
    for i, case in enumerate(gold, 1):
        game = case["game"]
        if game not in ("sr", "ys", "zzz"):
            continue
        data = load_game(game)
        qv = emb.embed([case["question"]])[0]
        gold_ids = {g["chunk_id"] for g in case["gold_chunks"]}
        plain = [r["id"] for r in vec_top(data["tbl"], qv, args.k)]
        rrf = rrf_top(game, case["question"], qv, args.k)
        rer = rerank_top(game, case["question"], qv, args.k)
        results.append({"case_id": case["case_id"], "gold": sorted(gold_ids), "plain": plain, "rrf": rrf, "rerank": rer})
        print(f"  [{i}/{len(gold)}] {case['case_id']} gold={len(gold_ids)}")

    def recall_at(key: str, k: int) -> float:
        vals = []
        for r in results:
            gold = set(r["gold"])
            if not gold:
                continue
            vals.append(len(set(r[key][:k]) & gold) / len(gold))
        return round(statistics.mean(vals), 4) if vals else 0.0

    summary = {
        "n": len(results),
        "note": "chunk gold is auto-generated (per gold page: most similar chunk to question)",
        "plain_vector": {f"recall@{k}": recall_at("plain", k) for k in (1, 3, 5)},
        "rrf": {f"recall@{k}": recall_at("rrf", k) for k in (1, 3, 5)},
        "rrf_rerank": {f"recall@{k}": recall_at("rerank", k) for k in (1, 3, 5)},
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
