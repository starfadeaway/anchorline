# -*- coding: utf-8 -*-
"""LoreKeeper 数据集桥接：用 LoreKeeper 的 chunk 索引 + 56 题评测集，跑 Anchorline 的检索策略。

- 数据源：`<lorekeeper>/backend/app/eval/cases.py`（EvalCase：question / gold_answer / gold_pages）
- 索引：`<lorekeeper>/data/lance/kb_<game>_baai-bge-m3_base`（chunk: id/text/page_title/vector 1024）
- 查询向量：BAAI/bge-m3（与 LoreKeeper 原生一致，保证公平）

两种检索口径：
  - `--mode chunk`（默认）：纯向量 / BM25+向量 RRF / RRF+rerank（chunk 级，去重成页面）
  - `--mode page`：页面级重排——向量召回 chunk → 按 page 聚合（每页取最高分）→ 对页面文本 rerank

指标：Recall@1/3/5、MRR（只算有 gold_pages 的题）。
用法：
  .venv\\Scripts\\python.exe scripts\\lorekeeper_bridge.py --mode page --k 5
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import jieba  # noqa: E402
import lancedb  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.llm import EmbeddingClient, ReaderConfig, rerank_client  # noqa: E402

LK = r"C:\Users\Liu\Desktop\ai实验\MiniMax\AI项目\lorekeeper"
LK_CASES = os.path.join(LK, "backend", "app", "eval", "cases.py")
LK_LANCE = os.path.join(LK, "data", "lance")
LK_EMBED = "BAAI/bge-m3"

_cache: dict[str, dict] = {}


def load_cases() -> list:
    spec = importlib.util.spec_from_file_location("lk_cases", LK_CASES)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lk_cases"] = mod  # dataclass 需要模块已注册
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.all_cases()


def load_game(game: str) -> dict:
    if game in _cache:
        return _cache[game]
    db = lancedb.connect(LK_LANCE)
    tbl = db.open_table(f"kb_{game}_baai-bge-m3_base")
    rows = tbl.to_arrow().select(["id", "page_title", "text"]).to_pylist()
    from rank_bm25 import BM25Plus

    tokens = [[t for t in jieba.lcut(r.get("text") or "") if t.strip()] for r in rows]
    _cache[game] = {"tbl": tbl, "rows": rows, "bm25": BM25Plus(tokens)}
    return _cache[game]


def embedder() -> EmbeddingClient:
    s = Settings()
    return EmbeddingClient(ReaderConfig(s.siliconflow_base_url, s.siliconflow_api_key, LK_EMBED))


def vector_search(tbl, vec: list[float], k: int) -> list[dict]:
    return tbl.search(vec).select(["id", "page_title", "text"]).limit(k).to_list()


def recall_at(retrieved: list[str], gold: list[str], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(retrieved[:k]) & set(gold)) / len(gold)


def mrr(retrieved: list[str], gold: list[str]) -> float:
    for i, page in enumerate(retrieved, 1):
        if page in gold:
            return 1.0 / i
    return 0.0


def dedupe_pages(rows: list[dict]) -> list[str]:
    pages: list[str] = []
    for r in rows:
        t = r.get("page_title") or ""
        if t and t not in pages:
            pages.append(t)
    return pages


def chunk_hybrid_pages(game: str, question: str, vec: list[float], k: int, use_rerank: bool) -> list[str]:
    data = load_game(game)
    tbl, rows, bm25 = data["tbl"], data["rows"], data["bm25"]
    tokens = [t for t in jieba.lcut(question) if t.strip()]
    scores = bm25.get_scores(tokens)
    bm_ids = [i for i in sorted(range(len(rows)), key=lambda i: -float(scores[i])) if scores[i] > 0][:30]
    vec_rows = vector_search(tbl, vec, 20)
    vec_ids = [r["id"] for r in vec_rows]

    id_to_row = {r["id"]: r for r in rows}
    rrf: dict[str, float] = {}
    for ids in (bm_ids, vec_ids):
        for rank, rid in enumerate(ids):
            rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (60 + rank + 1)
    fused = [rid for rid, _ in sorted(rrf.items(), key=lambda kv: -kv[1])][: 2 * k]
    cand = [id_to_row[rid] for rid in fused if rid in id_to_row]

    if use_rerank and len(cand) > 1:
        try:
            scored = rerank_client().rerank(question, [c["text"][:2000] for c in cand], top_n=k)
            cand = [cand[i] for i, _ in scored if 0 <= i < len(cand)]
        except Exception as e:
            print("  [warn] rerank failed:", str(e)[:80])
    return dedupe_pages(cand)[:k]


def page_rank_pages(game: str, question: str, vec: list[float], k: int, use_rerank: bool) -> list[str]:
    """页面级：chunk 向量召回 → 按 page 聚合（每页最高分）→ 对页面文本 rerank。"""
    data = load_game(game)
    vec_rows = vector_search(data["tbl"], vec, 80)
    pages: dict[str, dict] = {}
    for r in vec_rows:
        title = r.get("page_title") or ""
        if not title:
            continue
        dist = 1.0 - float(r.get("_distance") or 0.0)
        p = pages.setdefault(title, {"score": 0.0, "texts": []})
        p["score"] = max(p["score"], dist)
        p["texts"].append(r.get("text") or "")
    if not pages:
        return []
    if use_rerank and len(pages) > 1:
        titles = list(pages)
        docs = ["\n".join(pages[t]["texts"][:3])[:2000] for t in titles]
        try:
            scored = rerank_client().rerank(question, docs, top_n=k)
            return [titles[i] for i, _ in scored if 0 <= i < len(titles)][:k]
        except Exception as e:
            print("  [warn] page rerank failed:", str(e)[:80])
    return [t for t, _ in sorted(pages.items(), key=lambda kv: -kv[1]["score"])][:k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0=全部）")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--mode", choices=["chunk", "page"], default="chunk")
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cases = [c for c in load_cases() if c.gold_pages]
    if args.limit:
        cases = cases[: args.limit]
    print(f"cases with gold_pages: {len(cases)} | mode={args.mode}")

    emb = embedder()
    rows_out = []
    for i, case in enumerate(cases, 1):
        game = case.game
        if game not in ("sr", "ys", "zzz"):
            continue
        vec = emb.embed([case.question])[0]
        if args.mode == "page":
            plain = page_rank_pages(game, case.question, vec, args.k, use_rerank=False)
            hyb = page_rank_pages(game, case.question, vec, args.k, use_rerank=not args.no_rerank)
        else:
            data = load_game(game)
            plain = dedupe_pages(vector_search(data["tbl"], vec, args.k))[: args.k]
            hyb = chunk_hybrid_pages(game, case.question, vec, args.k, use_rerank=not args.no_rerank)
        rows_out.append({
            "case_id": case.case_id,
            "game": game,
            "question": case.question,
            "gold_pages": case.gold_pages,
            "plain_pages": plain,
            "hybrid_pages": hyb,
        })
        print(f"  [{i}/{len(cases)}] {case.case_id} gold={case.gold_pages[:2]} plain={plain[:2]} hybrid={hyb[:2]}")

    def agg(key: str, k: int) -> dict:
        return {
            **{f"recall@{x}": round(statistics.mean(recall_at(r[key], r["gold_pages"], x) for r in rows_out), 4) for x in (1, 3, 5)},
            "mrr": round(statistics.mean(mrr(r[key], r["gold_pages"]) for r in rows_out), 4),
        }

    summary = {"plain_pages": agg("plain_pages", 5), "hybrid_pages": agg("hybrid_pages", 5)}
    out = args.out or os.path.join(
        ROOT, "data", "eval", f"lorekeeper_bridge_{args.mode}{'_no_rerank' if args.no_rerank else ''}.json"
    )
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"n": len(rows_out), "k": args.k, "mode": args.mode, "summary": summary, "rows": rows_out}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
