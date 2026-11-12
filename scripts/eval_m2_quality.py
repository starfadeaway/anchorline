# -*- coding: utf-8 -*-
"""M2 记忆质量评测（用 V1 72 题的 gold，不新标）：

1. 回溯意图分类：query_form ∈ {current, retrospective}
2. 冲突裁决一致率：conflict_type ∈ {时效, 数值, 否定, 无}，expected_resolution ∈ {覆盖, 并存, 无法裁决}

输入：V1 会话原文（dataset/v1/minimax-package/questions/<id>.md，含 Question / Official answer / Session A/B）
输出：data/eval/m2_quality.json + reports/m2_quality.md
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
# X34：默认写 _drafts，避免一次复现覆盖已入库产物；--out/--md-out 可显式指定
OUT_JSON = os.path.join(ROOT, "data", "eval", "_drafts", "m2_quality.json")
OUT_MD = os.path.join(ROOT, "reports", "_drafts", "m2_quality.md")

SYS = "你是 LongMemEval-S knowledge-update 的标注器。只输出 JSON，不要解释。"

PROMPT = """请阅读下面的会话，判断三个字段，并只输出 JSON：
{{"query_form": "current|retrospective", "conflict_type": "时效|语义|偏好反转|无", "expected_resolution": "覆盖|并存|标失效|升级人工"}}

规则：
- query_form=current 表示问题问的是“当前值”；retrospective 表示问的是“过去/旧值”。
- conflict_type：
  * 时效 = 问题关于“新值是否取代旧值”（旧值被更新的时间顺序取代，**即使值是数字**）；
  * 语义 = 属性含义相近但值不同（非时效）；
  * 偏好反转 = 用户偏好从 A 变成 B；
  * 无 = 无冲突。
- expected_resolution：覆盖=应取新值；并存=两者都成立；标失效=旧值应标记失效；升级人工=无法自动裁决。
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
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0=全部）")
    ap.add_argument("--out", default=None, help="结果 JSON 路径（默认 _drafts）")
    ap.add_argument("--md-out", default=None, help="报告 md 路径（默认 _drafts）")
    ap.add_argument("--dry-run", action="store_true", help="只打印题数与路径，不调模型")
    args = ap.parse_args()
    out_json = args.out or OUT_JSON
    out_md = args.md_out or OUT_MD
    rows = [json.loads(line) for line in open(KU, encoding="utf-8") if line.strip()]
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    if args.dry_run:
        print(f"dry-run: rows={len(rows)} out_json={out_json} out_md={out_md}（未调用模型）")
        return 0
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
            if not extract_json(out):  # reasoning 模型可能把 token 花在思考上，空输出时放大重试
                out = client.complete(
                    [{"role": "system", "content": SYS}, {"role": "user", "content": PROMPT.format(context=context)}],
                    temperature=0.0,
                    max_tokens=4096,
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

    def valid_acc(key: str) -> float:
        vals = [
            1.0 if x["pred"][key] == x["gold"][key] else 0.0
            for x in results
            if x["gold"].get(key) and x["pred"].get(key)
        ]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary = {
        "n": len(results),
        "n_empty_pred": sum(1 for x in results if not x["pred"].get("query_form")),
        "query_form_acc": acc("query_form"),
        "conflict_type_acc": acc("conflict_type"),
        "expected_resolution_acc": acc("expected_resolution"),
        "query_form_acc_valid": valid_acc("query_form"),
        "conflict_type_acc_valid": valid_acc("conflict_type"),
        "expected_resolution_acc_valid": valid_acc("expected_resolution"),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, ensure_ascii=False, indent=1)

    lines = [
        f"> 样本量 n = {len(results)}；空预测数 n_empty_pred = {summary['n_empty_pred']}\n",
        "# M2 记忆质量评测（V1 72 题 gold）\n",
        "> 用 V1 的 72 题 gold 检验“系统自动判定”与人工标注的一致率；不新标、不改 gold。\n",
        "> **基线说明**：每个指标必须与「常数基线」（gold 众数占比）对照；零方差的 gold 字段（如 conflict_type=时效 72/72）",
        "> 常数预测器即 100%，此类指标不构成能力指标。\n",
        "> **两套口径**：严格 = gold 非空即计入；宽松 = 双方都非空才计入。\n",
        "| 指标 | 严格一致率 | 宽松一致率 |",
        "|---|---|---|",
        f"| query_form（回溯意图） | {summary['query_form_acc']:.4f} | {summary['query_form_acc_valid']:.4f} |",
        f"| conflict_type（冲突类型） | {summary['conflict_type_acc']:.4f} | {summary['conflict_type_acc_valid']:.4f} |",
        f"| expected_resolution（裁决） | {summary['expected_resolution_acc']:.4f} | {summary['expected_resolution_acc_valid']:.4f} |",
        "",
        "## 逐题差异（不一致项）\n",
        "| qid | 字段 | gold | pred |",
        "|---|---|---|---|",
    ]
    for x in results:
        for key in ("query_form", "conflict_type", "expected_resolution"):
            if x["gold"].get(key) and x["pred"].get(key) != x["gold"][key]:
                lines.append(f"| `{x['question_id']}` | {key} | {x['gold'][key]} | {x['pred'].get(key)} |")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", out_json, out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
