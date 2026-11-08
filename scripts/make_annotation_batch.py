# -*- coding: utf-8 -*-
"""生成下一批人工标注材料（v3 schema）。

输出（均在 dataset/v1/，本地保留、不入库）：
  manual15.md    15 道 manual_needed（优先判层），含两个 gold session 全文
  remaining48.md 44 current + 4 retrospective（批量标值），含两个 gold session 全文
  annotate-remaining-template.jsonl  63 行空白标注模板（预填 auto 字段，待人工填值/判层）

已标 9 题会被剔除：5a4f22c0 6aeb4375 830ce83f 852ce960 945e3d21 07741c44 50635ada 0ddfec37 6a1eabeb
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KU = os.path.join(ROOT, "dataset", "longmemeval_s_cleaned.json")
ANN = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
OUT = os.path.join(ROOT, "dataset", "v1")

DONE = {
    "5a4f22c0", "6aeb4375", "830ce83f", "852ce960", "945e3d21",
    "07741c44", "50635ada", "0ddfec37", "6a1eabeb",
}


def msg_lines(session):
    out = []
    for m in session or []:
        role = m.get("role", "?")
        content = str(m.get("content", "")).replace("\r", "")
        out.append(f"**{role}**: {content}")
    return "\n\n".join(out)


def main() -> int:
    ku = json.load(open(KU, encoding="utf-8"))
    qs = {q["question_id"]: q for q in ku if q.get("question_type") == "knowledge-update"}
    rows = [json.loads(l) for l in open(ANN, encoding="utf-8") if l.strip()]
    todo = [r for r in rows if r["question_id"] not in DONE]
    manual = [r for r in todo if r["query_form"] == "manual_needed"]
    batch = [r for r in todo if r["query_form"] != "manual_needed"]
    print(f"remaining={len(todo)} (manual={len(manual)}, batch={len(batch)})")
    os.makedirs(OUT, exist_ok=True)

    def write_md(path, title, items, note):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n> {note}\n> 材料含 gold session 原文，**不入库**。\n\n")
            f.write("## 清单\n\n")
            for n, r in enumerate(items, 1):
                f.write(f"{n}. `{r['question_id']}` — {r['query_form']}\n")
            f.write("\n---\n\n")
            for n, r in enumerate(items, 1):
                qid = r["question_id"]
                q = qs[qid]
                sess = q["haystack_sessions"]
                sid_list = q["haystack_session_ids"]
                dates = q["haystack_dates"]
                gold = list(q.get("answer_session_ids") or [])
                pos = sorted(gold, key=lambda s: sid_list.index(s))
                f.write(f"\n## {n:02d}. `{qid}` — {r['query_form']}\n\n")
                f.write(f"- **question**: {q['question']}\n")
                f.write(f"- **官方 answer**: `{q.get('answer')}`（`official_answer_role={r['official_answer_role']}`, `official_answer_session_index={r['official_answer_session_index']}`）\n")
                f.write(f"- **auto**: stale_source=`{r['stale_source_session_id']}`, new_source=`{r['new_source_session_id']}`, gold_session_index={r['gold_session_index']}\n")
                if r["query_form"] == "manual_needed":
                    f.write("- **待判**: query_form（current / retrospective / abstention）；旧值与当前值；session_order_source 记 manual\n")
                elif r["query_form"] == "current":
                    f.write("- **待填**: `stale_value`（旧值，通常在第 1 个 gold session）；确认 `new_value` = 官方 answer\n")
                else:
                    f.write("- **待填**: `new_value`（当前值，通常在较晚 session）；确认 `stale_value` = 官方 answer\n")
                f.write("\n")
                for sid in pos:
                    i = sid_list.index(sid)
                    f.write(f"### session `{sid}`（haystack idx {i}，{dates[i]}）\n\n")
                    f.write(msg_lines(sess[i]) + "\n\n")

    write_md(
        os.path.join(OUT, "manual15.md"),
        "V1-KU manual_needed 15 题（优先判层）",
        manual,
        "这批题自动定位失败（NEITHER/BOTH）。需要人工判 query_form 并找出旧值/当前值所在 session。",
    )
    write_md(
        os.path.join(OUT, "remaining48.md"),
        "V1-KU 剩余 48 题（批量标值）",
        batch,
        "current 44 题：只缺 stale_value；retrospective 4 题：只缺 new_value（当前值）。",
    )

    # 空白模板：预填 auto 字段，人工填值/判层
    tpl = os.path.join(OUT, "annotate-remaining-template.jsonl")
    with open(tpl, "w", encoding="utf-8") as f:
        for r in todo:
            row = {
                "question_id": r["question_id"],
                "query_form": r["query_form"],
                "new_value": r["new_value"],
                "official_answer": r["official_answer"],
                "official_answer_role": r["official_answer_role"],
                "official_answer_session_index": r["official_answer_session_index"],
                "stale_value": "",
                "stale_value_is_placeholder": False,
                "stale_source_session_id": r["stale_source_session_id"],
                "new_source_session_id": r["new_source_session_id"],
                "session_order_source": r["session_order_source"],
                "gold_session_index": r["gold_session_index"],
                "is_abstention": r["is_abstention"],
                "conflict_type": "",
                "expected_resolution": "",
                "entity": "",
                "match_mode": "",
                "note": "",
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("written:", os.path.join(OUT, "manual15.md"), os.path.join(OUT, "remaining48.md"), tpl)
    for p in ("manual15.md", "remaining48.md", "annotate-remaining-template.jsonl"):
        fp = os.path.join(OUT, p)
        print(f"  {p}: {os.path.getsize(fp)/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
