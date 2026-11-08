# -*- coding: utf-8 -*-
"""M1 退出标准验证：生产 L0 实现 vs measure_compression.py 的实测压缩比。

口径必须一致（误差 ≤ 20%）：
  - web 100 条轨迹（lme_v2_small.json 中 web 题引用的轨迹并集）
  - raw_chars = states[i].accessibility_tree 字符数之和
  - novel_chars = 同轨迹跨 state 行级去重后（行 + 1 换行）之和
  - token = chars / 4

用法：python scripts/verify_l0.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.memory.l0 import L0Deduper  # noqa: E402

V2 = os.path.join(ROOT, "dataset", "v2")
CPT = 4


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_traj(offs, tid, fh):
    if tid not in offs:
        return None
    fh.seek(offs[tid])
    return json.loads(fh.readline().decode("utf-8"))


def main():
    small = load(os.path.join(V2, "lme_v2_small.json"))
    offs = load(os.path.join(V2, "traj_offsets.json"))
    idx = load(os.path.join(V2, "traj_index.json"))
    qs = {}
    with open(os.path.join(V2, "questions.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                qs[q["id"]] = q

    web_qids = [qid for qid, q in qs.items() if str(q.get("environment", "")).startswith("webarena")]
    web_trajs = sorted({t for qid in web_qids for t in small.get(qid, []) if (idx.get(t) or {}).get("domain") == "web"})
    print(f"web 题 {len(web_qids)} 道；并集轨迹 {len(web_trajs)} 条")

    rows = []
    with open(os.path.join(V2, "trajectories.jsonl"), "rb") as fh:
        for tid in web_trajs:
            rec = get_traj(offs, tid, fh)
            if not rec:
                continue
            d = L0Deduper()
            raw = 0
            for st in rec.get("states") or []:
                if not isinstance(st, dict):
                    continue
                text = st.get("accessibility_tree") or ""
                raw += len(text)
                d.feed(text)
            novel = d.stats.novel_chars
            rows.append({
                "id": tid,
                "raw_tokens": raw // CPT,
                "novel_tokens": novel // CPT,
                "compression": (raw / novel) if novel else 0.0,
            })

    comp = sorted(r["compression"] for r in rows)
    med = statistics.median(comp)
    raw_sum = sum(r["raw_tokens"] for r in rows)
    novel_sum = sum(r["novel_tokens"] for r in rows)
    print(f"L0 复算：中位压缩比 {med:.2f}× | 原始 {raw_sum:,} tokens | 去重后 {novel_sum:,} tokens")

    stats_path = os.path.join(V2, "v2_compression_stats.json")
    if os.path.exists(stats_path):
        stats = load(stats_path)
        web = next((s for s in stats["summaries"] if s["label"] == "web"), None)
        if web:
            ref_med = web["compression"]["median"]
            ref_novel = web["novel_tokens"]["sum"]
            ref_raw = web["raw_tokens"]["sum"]
            d_med = abs(med - ref_med) / ref_med * 100
            d_novel = abs(novel_sum - ref_novel) / ref_novel * 100
            d_raw = abs(raw_sum - ref_raw) / ref_raw * 100
            print(f"参考（v2_compression_stats web）：中位 {ref_med:.2f}× | 原始 {ref_raw:,} | 去重后 {ref_novel:,}")
            print(f"差异：中位 {d_med:.2f}% | raw {d_raw:.2f}% | novel {d_novel:.2f}%")
            ok = d_med <= 20 and d_novel <= 20 and d_raw <= 20
            print("M1 判据（误差 ≤ 20%）：", "PASS" if ok else "FAIL")
            return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
