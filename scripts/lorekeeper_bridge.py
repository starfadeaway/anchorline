# -*- coding: utf-8 -*-
"""LoreKeeper 数据集桥接：用 LoreKeeper 的 chunk 索引 + 56 题评测集，跑 Anchorline 的混合检索。

- 数据源：`<lorekeeper>/backend/app/eval/cases.py`（EvalCase：question / gold_answer / gold_pages）
- 索引：`<lorekeeper>/data/lance/kb_<game>_baai-bge-m3_base`（chunk: id/text/page_title/vector 1024）
- 查询向量：BAAI/bge-m3（与 LoreKeeper 原生一致，保证公平）
- 对比：纯向量检索（LoreKeeper 原生口径） vs Anchorline 混合（BM25 + 向量 + RRF + BGE rerank）

指标：Recall@1/3/5、MRR（只算有 gold_pages 的题）。
用法：
  .venv\\Scripts\\python.exe scripts\\lorekeeper_bridge.py --limit 5
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

import lancedb  # noqa: E402
import jieba  # noqa: E402

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
    bm25 = BM25Plus(tokens)
    _cache[game] = {"tbl": tbl, "rows": rows, "bm25": bm25}
    return _cache[game]


def embedder() -> EmbeddingClient:
    s = Settings()
    return EmbeddingClient(ReaderConfig(s.siliconflow_base_url, s.siliconflow_api_key, LK_EMBED))


def vector_search(tbl, vec: list[float], k: int) -> list[dict]:
    return tbl.search(vec).select(["id", "page_title", "text"]).limit(k).to_list()


def recall_at(retrieved: list[str], gold: list[str], k: int) -> float:
    if not gold:
        return 0.0
    got = set(retrieved[:k])
    return len(got & set(gold)) / len(gold)


def mrr(retrieved: list[str], gold: list[str]) -> float:
    for i, page in enumerate(retrieved, 1):
        if page in gold:
            return 1.0 / i
    return 0.0


def hybrid_pages(game: str, question: str, vec: list[float], k: int, use_rerank: bool = True) -> list[str]:
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
        except Exception as e:  # 重排失败回退 RRF
            print("  [warn] rerank failed:", str(e)[:80])

    pages: list[str] = []
    for c in cand:
        title = c.get("page_title") or ""
        if title and title not in pages:
            pages.append(title)
    return pages[:k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0=全部）")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "eval", "lorekeeper_bridge.json"))
    args = ap.parse_args()

    cases = [c for c in load_cases() if c.gold_pages]
    if args.limit:
        cases = cases[: args.limit]
    print(f"cases with gold_pages: {len(cases)}")

    emb = embedder()
    rows_out = []
    for i, case in enumerate(cases, 1):
        game = case.game
        if game not in ("sr", "ys", "zzz"):
            print(f"  [{i}] {case.case_id} skip (game={game})")
            continue
        vec = emb.embed([case.question])[0]
        data = load_game(game)
        plain = vector_search(data["tbl"], vec, args.k)
        plain_pages = []
        for r in plain:
            t = r.get("page_title") or ""
            if t and t not in plain_pages:
                plain_pages.append(t)
        hyb_pages = hybrid_pages(game, case.question, vec, args.k, use_rerank=not args.no_rerank)
        row = {
            "case_id": case.case_id,
            "game": game,
            "question": case.question,
            "gold_pages": case.gold_pages,
            "plain_pages": plain_pages,
            "hybrid_pages": hyb_pages,
        }
        rows_out.append(row)
        print(f"  [{i}/{len(cases)}] {case.case_id} gold={case.gold_pages[:2]} plain={plain_pages[:2]} hybrid={hyb_pages[:2]}")

    def agg(key: str, k: int) -> tuple[float, float]:
        rec = statistics.mean(recall_at(r[key], r["gold_pages"], k) for r in rows_out)
        m = statistics.mean(mrr(r[key], r["gold_pages"]) for r in rows_out)
        return round(rec, 4), round(m, 4)

    summary = {}
    for name in ("plain_pages", "hybrid_pages"):
        summary[name] = {
            f"recall@{k}": agg(name, k)[0] for k in (1, 3, 5)
        } | {"mrr": agg(name, 5)[1]}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"n": len(rows_out), "k": args.k, "summary": summary, "rows": rows_out}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
