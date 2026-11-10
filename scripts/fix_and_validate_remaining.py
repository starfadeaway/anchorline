# -*- coding: utf-8 -*-
"""修正 + 校验 63 行标注（v3.1 规则）。

输入：dataset/v1/annotate-remaining-template.jsonl（用户已填）
输出：
  dataset/v1/annotations-remaining-fixed.jsonl  修正后的 63 行（待合并）
  dataset/v1/annotations-remaining-review.md    校验报告（errors / warnings）
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "dataset", "v1", "annotate-remaining-template.jsonl")
KU = os.path.join(ROOT, "dataset", "longmemeval_s_cleaned.json")
OUT_JSONL = os.path.join(ROOT, "dataset", "v1", "annotations-remaining-fixed.jsonl")
OUT_MD = os.path.join(ROOT, "dataset", "v1", "annotations-remaining-review.md")

# v3.1 修正（依据数据核实，见 remaining63-不确定标注说明.md 的 8 组）
FIXES = {
    "031748ae": {
        "query_form": "current",
        "note": "双槽位题归 current（v3.1 规则 8）；stale=4（S1 'team of 4 engineers'）、new=5（S2 'team of five engineers'）；官方复合句保留在 official_answer",
    },
    "c4ea545c": {
        "new_value": "four times a week",
        "note": "比较题：官方 answer=Yes 是结论；new_value 填具体当前值 four times a week（v3.1 规则 7）",
    },
    "22d2cb42": {
        "stale_value": None,
        "note": "旧状态=未送修（无旧值）；Rhythm Central 只是候选店，不算旧值（v3.1 规则 6）",
    },
    "5c40ec5b": {
        "stale_value": None,
        "note": "旧状态=未见面（无旧值），按 null 处理（v3.1 规则 6）",
    },
    "7e974930": {
        "note": "已核实：S2 user 原文 'I earned $420 at the Downtown Farmers Market on my most recent visit'；S1 列表最新 Downtown FM 为 May 6 $350。此前 note 说 $420 不在原文，已更正",
    },
}


def norm(s) -> str:
    return " ".join(str(s or "").lower().replace("-", " ").replace("_", " ").split())


def main() -> int:
    ku = json.load(open(KU, encoding="utf-8"))
    qs = {q["question_id"]: q for q in ku if q.get("question_type") == "knowledge-update"}
    rows = [json.loads(line) for line in open(SRC, encoding="utf-8") if line.strip()]

    errors, warnings = [], []
    seen = set()
    out = []
    for r in rows:
        qid = r["question_id"]
        if qid in seen:
            errors.append(f"{qid}: duplicate")
        seen.add(qid)
        q = qs.get(qid)
        if q is None:
            errors.append(f"{qid}: not a KU question")
            continue

        fix = FIXES.get(qid)
        if fix:
            for k, v in fix.items():
                if k == "note":
                    old = str(r.get("note") or "").strip()
                    r["note"] = (old + " | FIX: " + v) if old else v
                else:
                    r[k] = v

        qf = r.get("query_form")
        if qf not in {"current", "retrospective", "manual_needed", "abstention"}:
            errors.append(f"{qid}: bad query_form={qf}")
        if r.get("is_abstention") != qid.endswith("_abs"):
            errors.append(f"{qid}: is_abstention mismatch")

        if qid.endswith("_abs"):
            errors.append(f"{qid}: KU 72 不应含 abs 题")
            continue

        gold = list(q.get("answer_session_ids") or [])
        for key in ("stale_source_session_id", "new_source_session_id"):
            if r.get(key) not in gold:
                errors.append(f"{qid}: {key}={r.get(key)} not in {gold}")
        if r.get("gold_session_index") not in (0, 1):
            errors.append(f"{qid}: bad gold_session_index={r.get('gold_session_index')}")

        if qf == "current":
            if not str(r.get("new_value") or "").strip():
                errors.append(f"{qid}: current but new_value empty")
            if not str(r.get("stale_value") or "").strip() and r.get("stale_value") is not None:
                warnings.append(f"{qid}: current but stale_value empty")
            if norm(q.get("answer")) and norm(q.get("answer")) not in norm(r.get("new_value")):
                warnings.append(f"{qid}: new_value 不含官方 answer（可能是复合/结论答案，允许但需 note 说明）")
        elif qf == "retrospective":
            if not str(r.get("stale_value") or "").strip() and r.get("stale_value") is not None:
                errors.append(f"{qid}: retrospective but stale_value empty")
            if not str(r.get("new_value") or "").strip():
                errors.append(f"{qid}: retrospective but new_value empty")
            if norm(r.get("stale_value")) and norm(q.get("answer")) and norm(r.get("stale_value")) not in norm(q.get("answer")):
                warnings.append(f"{qid}: stale_value 不含官方 answer（确认方向或答案形式）")
        elif qf == "manual_needed":
            warnings.append(f"{qid}: 仍是 manual_needed，判层后才进 1a/1b")
        out.append(r)

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    cnt = Counter(r["query_form"] for r in out)
    null_stale = sum(1 for r in out if r.get("stale_value") is None)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# 63 行标注校验报告（v3.1）\n\n")
        f.write(f"- 行数：{len(out)}\n")
        f.write(f"- 分层：{dict(cnt)}\n")
        f.write(f"- stale_value=null（无旧值）：{null_stale}\n")
        f.write(f"- errors：{len(errors)}；warnings：{len(warnings)}\n\n")
        f.write("## Errors\n\n")
        f.write("\n".join(f"- {e}" for e in errors) or "（无）")
        f.write("\n\n## Warnings\n\n")
        f.write("\n".join(f"- {w}" for w in warnings) or "（无）")
        f.write("\n\n## 应用的修正\n\n")
        for qid, fx in FIXES.items():
            f.write(f"- `{qid}`: {', '.join(k for k in fx)}\n")

    print(f"rows={len(out)} forms={dict(cnt)} null_stale={null_stale} errors={len(errors)} warnings={len(warnings)}")
    if errors:
        for e in errors:
            print("  E:", e)
    for w in warnings[:20]:
        print("  W:", w)
    print("written:", OUT_JSONL, OUT_MD)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
