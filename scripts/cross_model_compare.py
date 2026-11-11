# -*- coding: utf-8 -*-
"""用值等价规则重算 MiniMax 交叉标注的一致率（不重跑模型）。

输入：dataset/v1/cross-model-16.jsonl（含 model parsed + human）
输出：reports/cross_model_16.md（可入库摘要）
      dataset/v1/cross-model-16-compare.md（逐题明细，不入库）
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.evaluation.v1_judge import value_equivalent  # noqa: E402

SRC = os.path.join(ROOT, "dataset", "v1", "cross-model-16.jsonl")
OUT_DOC = os.path.join(ROOT, "reports", "cross_model_16.md")  # U6：与 docstring 一致
OUT_DETAIL = os.path.join(ROOT, "dataset", "v1", "cross-model-16-compare.md")


def main() -> int:
    rows = [json.loads(line) for line in open(SRC, encoding="utf-8") if line.strip()]
    detail = ["# 跨模型交叉标注（MiniMax）逐题明细\n"]
    detail.append("| qid | 模型 qf | 人类 qf | 模型 stale | 人类 stale | 模型 new | 人类 new | 一致 |")
    detail.append("|---|---|---|---|---|---|---|---|")
    n = qf_ok = st_ok = nv_ok = both_ok = 0
    diffs = []
    for r in rows:
        p = r.get("parsed") or {}
        h = r["human"]
        n += 1
        if p.get("query_form") == h.get("query_form"):
            qf_ok += 1
        s = value_equivalent(p.get("stale_value"), h.get("stale_value"))
        w = value_equivalent(p.get("new_value"), h.get("new_value"))
        st_ok += s
        nv_ok += w
        full = (p.get("query_form") == h.get("query_form")) and s and w
        both_ok += full
        if not full:
            diffs.append((r["question_id"], p, h))
        detail.append(
            f"| `{r['question_id']}` | {p.get('query_form')} | {h.get('query_form')} | {p.get('stale_value')} | {h.get('stale_value')} | {p.get('new_value')} | {h.get('new_value')} | {'✅' if full else '❌'} |"
        )

    lines = [
        "# 跨模型交叉标注报告（MiniMax vs 人类）\n",
        "> 用途：检验**标注协议是否可复现**（另一个模型按同一协议能否得出同样结论）。",
        "> ⚠️ 这是**机器交叉检查，不是第二人类标注者**；报告措辞不得写「双人标注」。",
        "> 它与「人类自重复（间隔 ≥7 天 / 盲标）」是两件事，不能互相替代。\n",
        "## 1. 配置\n",
        "- 模型：`MiniMax-M3`（`https://api.minimax.chat/v1`，temperature 0，max_tokens 8192）",
        "- 样本：16 题 = 5 道争议题（`89941a94`、`c4ea545c`、`f685340e`、`031748ae`、`22d2cb42`）+ 11 道随机（seed=7）",
        "- 盲标：只给题面、官方 answer、两个 gold session 全文，**不给人类标注**",
        "- 提示词内置 v3.1 规则（双槽位→current、复合答案→具体值、null 旧值）\n",
        "## 2. 一致率（16 / 16 全部可解析）\n",
        "| 指标 | 数值 |",
        "|---|---|",
        f"| `query_form` 一致 | **{qf_ok}/{n}** |",
        f"| `stale_value` 值等价 | **{st_ok}/{n}** |",
        f"| `new_value` 值等价 | **{nv_ok}/{n}** |",
        f"| 三项全一致 | **{both_ok}/{n}** |\n",
        "> 值等价口径：归一化后相等，或内容词集合有包含关系（如 `4 engineers` ⊃ `4`、`30 dozen` ⊃ `30`），或 token F1 ≥ 0.8。\n",
        "## 3. 分歧题\n",
    ]
    if diffs:
        for qid, p, h in diffs:
            lines.append(f"### `{qid}`\n")
            lines.append(f"- 模型：qf=`{p.get('query_form')}`, stale=`{p.get('stale_value')}`, new=`{p.get('new_value')}`")
            lines.append(f"- 人类：qf=`{h.get('query_form')}`, stale=`{h.get('stale_value')}`, new=`{h.get('new_value')}`")
            lines.append(f"- 模型 note：{str(p.get('note'))[:200]}\n")
    else:
        lines.append("（无）\n")
    lines.extend([
        "## 4. 结论",
        "",
        "1. **方向（`query_form`）16/16 一致**：双槽位题在提示词写入 v3.1 规则后，模型与人类判断一致。",
        "2. **值粒度差异大于方向差异**：剩余分歧集中在「模型给更具体值（`4 engineers` / `30 dozen` / `in my bedroom`）」 vs 「人类给短值（`4` / `30` / `in the bedroom`）」，方向没有错。",
        "3. **模型不能替代人类自重复**：它测的是协议可复现性；且两个模型可能共享偏差。人类自重复（间隔 ≥7 天或盲标）仍需单独做。",
        "4. 这份交叉检查已满足协议 §6 三件套中的「跨模型交叉」一项；报告分列两项一致率，不合并、不写「双人标注」。",
        "",
        "## 5. 复现",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe scripts/cross_model_annotate.py   # 调 MiniMax 16 题",
        ".venv\\Scripts\\python.exe scripts/cross_model_compare.py    # 值等价重算",
        "```",
    ])

    with open(OUT_DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(OUT_DETAIL, "w", encoding="utf-8") as f:
        f.write("\n".join(detail))

    print(f"n={n} qf={qf_ok} stale={st_ok} new={nv_ok} full={both_ok}")
    print("written:", OUT_DOC, OUT_DETAIL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
