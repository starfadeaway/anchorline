# -*- coding: utf-8 -*-
"""§12.2：用产品侧混合检索（BM25 + 向量 + RRF + rerank）在 154 题上跑 D 臂，对照纯向量 D。

输出 data/eval/d_arm_154_hybrid.json + reports/d_arm_154_hybrid.md，并写 eval_runs（arm=D_hybrid）。

用法：.venv\\Scripts\\python.exe scripts/eval_hybrid_arm.py --limit 154
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.evaluation.metrics import score_deterministic  # noqa: E402
from anchorline.evaluation.pilot import sample_deterministic  # noqa: E402
from anchorline.evaluation.reader import build_messages  # noqa: E402
from anchorline.llm import embedding_client, reader_client, rerank_client  # noqa: E402
from anchorline.memory.l3 import assemble_blocks  # noqa: E402
from anchorline.retrieval.baseline import format_query_for_embedding, normalize_vector  # noqa: E402
from anchorline.retrieval.hybrid import rrf_fuse, tokenize  # noqa: E402
from anchorline.retrieval.store import open_table  # noqa: E402

TABLE = "v2_web_states_d"
OUT_JSON = os.path.join(ROOT, "data", "eval", "_drafts", "hybrid.json")
OUT_MD = os.path.join(ROOT, "reports", "_drafts", "hybrid.md")
REF = os.path.join(ROOT, "data", "eval", "d_arm_154_run3.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=154)
    ap.add_argument("--table", default=TABLE)
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--pool", type=int, default=50)
    ap.add_argument("--budget", type=int, default=4000)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--md-out", default=OUT_MD)
    args = ap.parse_args()

    sample = sample_deterministic(limit=args.limit, seed=0)
    tbl = open_table(args.table)
    rows = tbl.to_arrow().to_pylist()
    texts = [str(r.get("text") or "") for r in rows]
    keys = [f"{r.get('traj_id')}|{r.get('state_index')}" for r in rows]
    by_key = {k: r for k, r in zip(keys, rows)}
    from rank_bm25 import BM25Plus

    tokenized = [tokenize(t) for t in texts]
    bm = BM25Plus(tokenized)

    reader = reader_client(Settings())
    embedder = embedding_client(Settings())
    reranker = rerank_client()

    results = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        question = q["question"]
        # 1) BM25 全表
        q_tokens = tokenize(question)
        bm_scores = bm.get_scores(q_tokens)
        bm_order = sorted(range(len(rows)), key=lambda j: -float(bm_scores[j]))
        bm_rank = [keys[j] for j in bm_order[: args.pool] if bm_scores[j] > 0]
        # 2) 向量 top pool（LanceDB）
        qv = normalize_vector(embedder.embed([format_query_for_embedding(question)])[0])
        vec_hits = tbl.search(qv).limit(args.pool).to_list()
        vec_rank = [f"{h.get('traj_id')}|{h.get('state_index')}" for h in vec_hits]
        # 3) RRF 融合
        fused = rrf_fuse([bm_rank, vec_rank], k=60, top=20)
        candidates = [by_key[k] for k in fused if k in by_key][:20]
        if not candidates:
            hits = []
        else:
            # 4) rerank 取 top-k
            scored = reranker.rerank(question, [c["text"][:2000] for c in candidates], top_n=args.top_k)
            hits = [candidates[idx] for idx, _ in scored if 0 <= idx < len(candidates)][: args.top_k]

        items: list[tuple[float, str]] = []
        for h in hits:
            sim = 1.0 - float(h.get("_distance") or 0.0) if "_distance" in h else 0.0
            block = (
                f"### Memory entry\n"
                f"- Trajectory: {h.get('traj_id')}\n"
                f"- Goal: {h.get('goal', '')}\n"
                f"- State index: {h.get('state_index')}\n"
                f"- Similarity: {sim:.4f}\n\n"
                f"{h.get('text', '')}\n"
            )
            items.append((sim, block))
        context, used_tokens, dropped = assemble_blocks(items, args.budget)
        context = context or "(empty)"
        answer = reader.complete(build_messages(question, context), temperature=1.0, max_tokens=8192)
        score = 1 if score_deterministic(answer, q.get("answer"), q["eval_function"]) else 0
        results.append({"question_id": q["id"], "scores": [score], "mean": score, "context_tokens_mean": used_tokens})
        print(f"  [{i}/{len(sample)}] {q['id']} score={score} tokens={used_tokens} {time.time() - t0:.0f}s")

    summary = {
        "config": {"arm": "D_hybrid_bm25_vector_rrf_rerank", "table": args.table, "top_k": args.top_k,
                   "budget_tokens": args.budget, "reader_model": Settings().deepseek_reader_model, "temperature": 1.0},
        "d_hybrid_accuracy": statistics.mean(r["mean"] for r in results),
        "per_question": results,
        "elapsed_s": round(time.time() - t0, 1),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)

    # 对照纯向量 D（run3）
    lines = ["# D 臂混合检索对照（154 题）", "",
             "> D_hybrid = 产品侧检索（BM25 + 向量 + RRF + rerank）在同一 state 表上取 top-6；其余与 D 完全一致。", ""]
    ref = None
    if os.path.exists(REF):
        ref = json.load(open(REF, encoding="utf-8"))
        ref_map = {r["question_id"]: r["mean"] for r in ref.get("per_question", [])}
        cur_map = {r["question_id"]: r["mean"] for r in results}
        common = sorted(set(ref_map) & set(cur_map))
        diffs = [cur_map[q] - ref_map[q] for q in common]
        from eval_stats import sign_flip_exact

        lines += [
            "| 指标 | 纯向量 D（run3） | **D_hybrid** |",
            "|---|---|---|",
            f"| 准确率 | {statistics.mean([ref_map[q] for q in common]):.4f} | **{statistics.mean([cur_map[q] for q in common]):.4f}** |",
            "",
            f"配对差（hybrid − 纯向量）= {np.mean(diffs):+.4f}，精确符号翻转 p = {sign_flip_exact(diffs):.4f}（n={len(common)}）",
        ]
        summary["ref_mean"] = statistics.mean([ref_map[q] for q in common])
        summary["paired_diff_vs_vector"] = float(np.mean(diffs))
        summary["paired_p_exact"] = float(sign_flip_exact(diffs))
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1, default=float)
    os.makedirs(os.path.dirname(args.md_out), exist_ok=True)
    with open(args.md_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps({k: v for k, v in summary.items() if k != "per_question"}, ensure_ascii=False, indent=1, default=float))
    print("written:", args.out, args.md_out)
    print("提示：默认写到 _drafts/ 草稿目录（已 gitignore），不会覆盖正式报告/CI 输入；要更新正式产物请显式 --out/--md-out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
