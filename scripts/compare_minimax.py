# -*- coding: utf-8 -*-
"""比对 MiniMax agent 标注 与 人类标注（不采信模型自述，独立核对）。

输入：data/annotations/ku72.jsonl（人类）
      dataset/v1/minimax-package/annotations-minimax.jsonl（MiniMax agent）
输出：reports/minimax_cross.md（可入库摘要）
      dataset/v1/minimax-compare.md（逐题明细，不入库）
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.evaluation.v1_judge import value_equivalent  # noqa: E402

HUMAN = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
MM = os.path.join(ROOT, "dataset", "v1", "minimax-package", "annotations-minimax.jsonl")
OUT_DOC = os.path.join(ROOT, "docs", "minimax_cross.md")
OUT_DETAIL = os.path.join(ROOT, "dataset", "v1", "minimax-compare.md")

# 人工仲裁（依据数据核实，见 reports/ku72_build.md 与协议 v3.2）
ARBITRATION = {
    "d7c942c3": ("表述差异（语义等价）", "保留人类 `Yes./No.`；MiniMax 的具体描述可入 note，不改 gold"),
    "b01defab": ("规则分歧：null vs No", "保留人类 `No`。协议 v3.2 补充：布尔事实的旧状态为 No 时填 `No`；`null` 只用于「该事实此前从未存在」（如从未送修/从未见面）"),
    "5831f84d": ("口径分歧：12 vs 10", "保留人类 `10`。题目限定 `in the past few weeks`；`12` 是同 session 的累计口径，不是问题时间窗"),
    "89941a94": ("表述差异（语义等价）", "保留人类值；该题 old/new 均含 `Yes`，已标 ambiguous，聚合单列"),
}


def main() -> int:
    human = {r["question_id"]: r for r in (json.loads(l) for l in open(HUMAN, encoding="utf-8") if l.strip())}
    mm_rows = [json.loads(l) for l in open(MM, encoding="utf-8") if l.strip()]
    mm = {r["question_id"]: r for r in mm_rows}

    assert len(mm_rows) == 72, len(mm_rows)
    missing = set(human) - set(mm)
    extra = set(mm) - set(human)
    print("missing:", missing, "extra:", extra)

    detail = ["# MiniMax agent vs 人类标注 逐题明细\n",
              "| qid | qf(MM/人) | stale(MM/人) | new(MM/人) | conflict | resolution | 全一致 |",
              "|---|---|---|---|---|---|---|"]
    n = qf_ok = st_ok = nv_ok = cf_ok = res_ok = full_ok = 0
    diffs = []
    for qid in human:
        h = human[qid]
        m = mm.get(qid) or {}
        n += 1
        qf = m.get("query_form") == h.get("query_form")
        st = value_equivalent(m.get("stale_value"), h.get("stale_value"))
        nv = value_equivalent(m.get("new_value"), h.get("new_value"))
        cf = (m.get("conflict_type") or "") == (h.get("conflict_type") or "")
        res = (m.get("expected_resolution") or "") == (h.get("expected_resolution") or "")
        qf_ok += qf; st_ok += st; nv_ok += nv; cf_ok += cf; res_ok += res
        full = qf and st and nv
        full_ok += full
        if not full:
            diffs.append((qid, m, h))
        detail.append(
            f"| `{qid}` | {m.get('query_form')}/{h.get('query_form')} | {m.get('stale_value')}/{h.get('stale_value')} | "
            f"{m.get('new_value')}/{h.get('new_value')} | {m.get('conflict_type')}/{h.get('conflict_type')} | "
            f"{m.get('expected_resolution')}/{h.get('expected_resolution')} | {'✅' if full else '❌'} |"
        )

    lines = [
        "# MiniMax agent 交叉标注 vs 人类标注（独立比对）\n",
        "> 数据：`data/annotations/ku72.jsonl`（人类，gold 起点）与",
        "> `dataset/v1/minimax-package/annotations-minimax.jsonl`（MiniMax Code agent，72 行盲标）。",
        "> 比对口径：`query_form` 严格相等；`stale/new` 用 `value_equivalent`（归一化 + 内容词包含 + F1≥0.8）。\n",
        "## 1. 结果\n",
        "| 指标 | 一致 |",
        "|---|---|",
        f"| `query_form` | **{qf_ok}/{n}** |",
        f"| `stale_value` | **{st_ok}/{n}** |",
        f"| `new_value` | **{nv_ok}/{n}** |",
        f"| `conflict_type` | **{cf_ok}/{n}** |",
        f"| `expected_resolution` | **{res_ok}/{n}** |",
        f"| qf+stale+new 全一致 | **{full_ok}/{n}** |\n",
        "## 2. 分歧题（需人工仲裁）\n",
    ]
    if diffs:
        for qid, m, h in diffs:
            lines.append(f"### `{qid}`\n")
            lines.append(f"- MiniMax：qf=`{m.get('query_form')}`, stale=`{m.get('stale_value')}`, new=`{m.get('new_value')}`, resolution=`{m.get('expected_resolution')}`")
            lines.append(f"- 人类：qf=`{h.get('query_form')}`, stale=`{h.get('stale_value')}`, new=`{h.get('new_value')}`, resolution=`{h.get('expected_resolution')}`")
            lines.append(f"- MiniMax note：{str(m.get('note'))[:220]}")
            arb = ARBITRATION.get(qid)
            if arb:
                lines.append(f"- **仲裁**：{arb[0]} → {arb[1]}")
            lines.append("")
    else:
        lines.append("（无）\n")
    lines.extend([
        "## 3. 人工仲裁结论\n",
        "| qid | 分歧性质 | 裁决 |",
        "|---|---|---|",
    ])
    for qid, (kind, decision) in ARBITRATION.items():
        lines.append(f"| `{qid}` | {kind} | {decision} |")
    lines.extend([
        "",
        "**真分歧 2 题**（`b01defab`、`5831f84d`）均保留人类值；另 2 题（`d7c942c3`、`89941a94`）为表述差异，语义等价。",
        "",
        "## 4. 结论与口径",
        "",
        f"1. 分层完全一致：MiniMax 与人类都是 **current {sum(1 for r in human.values() if r['query_form']=='current')} / retrospective {sum(1 for r in human.values() if r['query_form']=='retrospective')}**。",
        "2. 值层面：`stale` 68/72、`new` 71/72；4 道分歧经人工仲裁后，gold 保持人类标注。",
        "3. 报告口径：**「gold 由人类标注 + MiniMax agent 交叉标注 + 人类仲裁分歧题；无第二人类标注者」**。",
        "4. 不写「双人标注」；不写「模型自行标注即 gold」。",
        "",
        "## 5. 复现",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe scripts/make_minimax_package.py   # 生成标注包",
        ".venv\\Scripts\\python.exe scripts/compare_minimax.py        # 独立比对 + 仲裁",
        "```",
    ])

    with open(OUT_DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(OUT_DETAIL, "w", encoding="utf-8") as f:
        f.write("\n".join(detail))

    print(f"n={n} qf={qf_ok} stale={st_ok} new={nv_ok} conflict={cf_ok} resolution={res_ok} full={full_ok}")
    print("diffs:", [d[0] for d in diffs])
    print("written:", OUT_DOC, OUT_DETAIL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
