# -*- coding: utf-8 -*-
"""对 72 条标注做判定规则自检，并生成规则文档。

自检逻辑：
  - 正例：用 stale_value 当 prediction → 应命中（judge_used_stale=True）
  - 负例：用 new_value 当 prediction → 应不命中（False）
  - 三档：exact / normalized / fuzzy(0.7 / 0.8 / 0.9)
  - 跳过：stale_value=null（无旧值）、stale_value_is_placeholder=true（占位）
  - 单列：old/new 共享结论词（Yes/No）或 F1 高 → 区分度弱

输出：docs/v1_judge_rules.md
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.evaluation.v1_judge import (  # noqa: E402
    is_ambiguous_record,
    judge_used_stale,
)

ANN = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
OUT = os.path.join(ROOT, "docs", "v1_judge_rules.md")

CONFIGS = [
    ("exact", "exact", 0.8),
    ("normalized", "normalized", 0.8),
    ("fuzzy@0.7", "fuzzy", 0.7),
    ("fuzzy@0.8", "fuzzy", 0.8),
    ("fuzzy@0.9", "fuzzy", 0.9),
]


def main() -> int:
    rows = [json.loads(line) for line in open(ANN, encoding="utf-8") if line.strip()]
    stale_rows = [r for r in rows if r.get("stale_value") is not None and not r.get("stale_value_is_placeholder")]
    skipped = [r for r in rows if r not in stale_rows]
    ambiguous = [r for r in rows if is_ambiguous_record(r)]

    results = []
    for label, mode, thr in CONFIGS:
        pos = sum(1 for r in stale_rows if judge_used_stale(r["stale_value"], r, mode=mode, fuzzy_threshold=thr)["used_stale"])
        neg = sum(1 for r in stale_rows if judge_used_stale(str(r.get("new_value") or ""), r, mode=mode, fuzzy_threshold=thr)["used_stale"])
        fp = [r["question_id"] for r in stale_rows
              if judge_used_stale(str(r.get("new_value") or ""), r, mode=mode, fuzzy_threshold=thr)["used_stale"]]
        results.append({"label": label, "mode": mode, "thr": thr,
                        "pos": pos, "pos_total": len(stale_rows),
                        "neg_fp": neg, "fp_ids": fp})

    lines = []
    lines.append("# V1-KU 判定规则（v1，已对 72 条标注自检）\n")
    lines.append("> 代码：`src/anchorline/evaluation/v1_judge.py`；单测：`tests/test_v1_judge.py`")
    lines.append("> 自检脚本：`scripts/audit_ku72_judge.py`；数据：`data/annotations/ku72.jsonl`\n")
    lines.append("## 1. 三档定义\n")
    lines.append("| 档 | 定义 | 用途 |")
    lines.append("|---|---|---|")
    lines.append("| `exact` | 小写 + 去标点 + **token 边界**子串命中 | 最严格，误判最少 |")
    lines.append("| `normalized` | exact + 英文数字词转阿拉伯数字 + 去 `$`/千分位 | **默认档** |")
    lines.append("| `fuzzy` | token 级 F1 ≥ 阈值（0.7/0.8/0.9） | 只作敏感性分析 |\n")
    lines.append("## 2. 跳过与单列规则\n")
    lines.append(f"- **跳过**（不进过期事实率）：`stale_value=null` 或 `stale_value_is_placeholder=true`，共 {len(skipped)} 题：")
    for r in skipped:
        lines.append(f"  - `{r['question_id']}`（{r.get('note','')[:60]}）")
    lines.append("- **单列**（old/new 共享结论词或 F1 高，区分度弱）：")
    for r in ambiguous:
        lines.append(f"  - `{r['question_id']}`：stale=`{r['stale_value']}` / new=`{r['new_value']}`")
    lines.append("")
    lines.append("## 3. 自检结果\n")
    lines.append(f"参与自检的有效题：**{len(stale_rows)} / {len(rows)}**（跳过 {len(skipped)}）。")
    lines.append("正例 = 用 `stale_value` 当 prediction；负例 = 用 `new_value` 当 prediction。\n")
    lines.append("| 档 | 正例命中 | 负例误命中 | 误命中题 |")
    lines.append("|---|---|---|---|")
    for x in results:
        ids = ", ".join(f"`{i}`" for i in x["fp_ids"][:8]) or "—"
        lines.append(f"| {x['label']} | {x['pos']}/{x['pos_total']} | {x['neg_fp']} | {ids} |")
    lines.append("")
    lines.append("## 4. 结论与建议\n")
    best = results[1]
    lines.append(f"- **默认档 = `normalized`**：正例 {best['pos']}/{best['pos_total']}，负例误命中 {best['neg_fp']}。")
    lines.append("- `exact` 与 `normalized` 的差值主要来自数字词/货币格式（`four` vs `4`、`$400,000` vs `400000`），不是判定分歧。")
    lines.append("- `fuzzy` 档的负例误命中来自 old/new 部分重叠（复合答案题），因此 **fuzzy 只用于敏感性分析，不作主判定**。")
    lines.append("- 若 0.7/0.8/0.9 三档结论翻转，报告必须写明「判定规则不稳健」，不得改数字。")
    lines.append("- `89941a94`（old/new 都是 Yes）与复合答案题的过期检测区分度弱，聚合时单列。\n")
    lines.append("## 5. 复现\n")
    lines.append("```powershell")
    lines.append(".venv\\Scripts\\python.exe -m pytest -q tests/test_v1_judge.py")
    lines.append(".venv\\Scripts\\python.exe scripts/audit_ku72_judge.py")
    lines.append("```")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    for x in results:
        print(f"{x['label']:14s} pos={x['pos']}/{x['pos_total']} neg_fp={x['neg_fp']} ids={x['fp_ids']}")
    print("skipped:", [r["question_id"] for r in skipped])
    print("ambiguous:", [r["question_id"] for r in ambiguous])
    print("written:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
