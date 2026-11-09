# -*- coding: utf-8 -*-
"""M2 记忆质量评测（用 V1 72 题的 gold，不新标）：

1. 回溯意图分类：query_form ∈ {current, retrospective}
2. 冲突裁决一致率：conflict_type ∈ {时效, 数值, 否定, 无}，expected_resolution ∈ {覆盖, 并存, 无法裁决}

输入：V1 会话原文（dataset/v1/minimax-package/questions/<id>.md，含 Question / Official answer / Session A/B）
输出：data/eval/m2_quality.json + docs/m2_quality.md
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.config import Settings  # noqa: E402
from anchorline.llm import reader_client  # noqa: E402

KU = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
MD_DIR = os.path.join(ROOT, "dataset", "v1", "minimax-package", "questions")
OUT_JSON = os.path.join(ROOT, "data", "eval", "m2_quality.json")
OUT_MD = os.path.join(ROOT, "docs", "m2_quality.md")

SYS = "你是 LongMemEval-S knowledge-update 的标注器。只输出 JSON，不要解释。"

PROMPT = """请阅读下面的会话，判断三个字段，并只输出 JSON：
{{"query_form": "current|retrospective", "conflict_type": "时效|数值|否定|无", "expected_resolution": "覆盖|并存|无法裁决"}}

规则：
- query_form=current 表示问题问的是“当前值”；retrospective 表示问的是“过去/旧值”。
- conflict_type：时效=新值覆盖旧值；数值=数值冲突；否定=是/否反转；无=无冲突。
- expected_resolution：覆盖=应取新值；并存=两者都成立；无法裁决=无法确定。
- 判新旧只看 A/B 顺序，不要用日期。

会话：
{context}
"""


def extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def main() -> int:
    rows = [json.loads(line) for line in open(KU, encoding="utf-8") if line.strip()]
    client = reader_client(Settings())
    results = []
    for i, r in enumerate(rows, 1):
        qid = r["question_id"]
        md_path = os.path.join(MD_DIR, f"{qid}.md")
        if not os.path.exists(md_path):
            print(f"  [{i}] {qid} skip (no md)")
            continue
        context = open(md_path, encoding="utf-8").read()[:12000]
        try:
            out = client.complete(
                [{"role": "system", "content": SYS}, {"role": "user", "content": PROMPT.format(context=context)}],
                temperature=0.0,
                max_tokens=2048,
            )
        except Exception as e:
            print(f"  [{i}] {qid} call failed: {str(e)[:80]}")
            out = ""
        parsed = extract_json(out) or {}
        gold = {
            "query_form": r.get("query_form"),
            "conflict_type": r.get("conflict_type"),
            "expected_resolution": r.get("expected_resolution"),
        }
        pred = {
            "query_form": parsed.get("query_form"),
            "conflict_type": parsed.get("conflict_type"),
            "expected_resolution": parsed.get("expected_resolution"),
        }
        results.append({"question_id": qid, "gold": gold, "pred": pred, "raw": out[:300]})
        print(f"  [{i}/{len(rows)}] {qid} qf={pred['query_form']}(gold {gold['query_form']}) ct={pred['conflict_type']} res={pred['expected_resolution']}")

    def acc(key: str) -> float:
        vals = [1.0 if x["pred"][key] == x["gold"][key] else 0.0 for x in results if x["gold"].get(key)]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary = {
        "n": len(results),
        "query_form_acc": acc("query_form"),
        "conflict_type_acc": acc("conflict_type"),
        "expected_resolution_acc": acc("expected_resolution"),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, ensure_ascii=False, indent=1)

    lines = [
        "# M2 记忆质量评测（V1 72 题 gold）\n",
        "> 用 V1 的 72 题 gold 检验“系统自动判定”与人工标注的一致率；不新标、不改 gold。\n",
        "| 指标 | 一致率 |",
        "|---|---|",
        f"| query_form（回溯意图） | {summary['query_form_acc']:.4f} |",
        f"| conflict_type（冲突类型） | {summary['conflict_type_acc']:.4f} |",
        f"| expected_resolution（裁决） | {summary['expected_resolution_acc']:.4f} |",
        "",
        "## 逐题差异（不一致项）\n",
        "| qid | 字段 | gold | pred |",
        "|---|---|---|---|",
    ]
    for x in results:
        for key in ("query_form", "conflict_type", "expected_resolution"):
            if x["gold"].get(key) and x["pred"].get(key) != x["gold"][key]:
                lines.append(f"| `{x['question_id']}` | {key} | {x['gold'][key]} | {x['pred'].get(key)} |")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
