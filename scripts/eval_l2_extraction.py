# -*- coding: utf-8 -*-
"""L2 事实抽取评测：让 reader 从 V1 会话中抽取事实，对比 ku72 的 gold（new_value 命中率）。

指标：
- value_hit_rate：gold new_value（归一化）出现在任一抽取 value 中的题数占比；
- avg_facts：平均抽取事实数；
- parse_fail：JSON 解析失败题数。

输出：data/eval/m2_l2_extraction.json + reports/m2_l2_extraction.md
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
OUT_JSON = os.path.join(ROOT, "data", "eval", "_drafts", "m2_l2_extraction.json")  # U3：默认不覆盖已入库产物
OUT_MD = os.path.join(ROOT, "reports", "_drafts", "m2_l2_extraction.md")

SYS = "你是事实抽取器。只输出 JSON，不要解释。"
PROMPT = """从下面的会话中抽取「用户的事实」（entity / attribute / value 三段式），只输出 JSON：
{{"facts": [{{"entity": "user", "attribute": "属性名", "value": "具体值"}}]}}

规则：
- 只抽用户陈述的事实，不抽助手建议；
- 每个事实一个条目；属性名简短（如 5k_pb、鞋的位置、喜欢的球队）；
- 值保留原文的具体值（数字/字符串）；
- 没有事实就输出 {{"facts": []}}。

会话：
{context}
"""


API_FAILS = 0


def norm(x) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(x or "").lower()).strip()


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
    parse_fail = 0
    for i, r in enumerate(rows, 1):
        qid = r["question_id"]
        md = os.path.join(MD_DIR, f"{qid}.md")
        if not os.path.exists(md):
            continue
        context = open(md, encoding="utf-8").read()[:9000]
        try:
            out = client.complete(
                [{"role": "system", "content": SYS}, {"role": "user", "content": PROMPT.format(context=context)}],
                temperature=0.0,
                max_tokens=4096,
            )
        except Exception as exc:
            global API_FAILS
            API_FAILS += 1
            print(f"  WARN api failed: {exc}")
            out = ""
        parsed = extract_json(out)
        if parsed is None:
            parse_fail += 1
            facts = []
        else:
            facts = parsed.get("facts") or []
        gold_value = norm(r.get("new_value"))
        hit = any(gold_value and gold_value in norm(f.get("value")) for f in facts) if gold_value else False
        results.append({"question_id": qid, "gold_value": r.get("new_value"), "facts": facts, "hit": hit})
        print(f"  [{i}/{len(rows)}] {qid} facts={len(facts)} hit={hit}")

    n = len(results)
    if n == 0:  # U4：一条都没跑 ≠ 全错
        raise SystemExit("没有可评测的题目：dataset/v1/minimax-package/questions 是否已准备？")
    summary = {
        "n": n,
        "value_hit_rate": round(sum(1 for x in results if x["hit"]) / n, 4) if n else 0.0,
        "avg_facts": round(sum(len(x["facts"]) for x in results) / n, 2) if n else 0.0,
        "parse_fail": parse_fail,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, ensure_ascii=False, indent=1)

    lines = [
        "# L2 事实抽取评测（V1 72 题）\n",
        "> 用 reader 从会话中抽取事实，与 ku72 的 gold `new_value` 比对（归一化子串命中）；非人工评审。\n",
        "| 指标 | 值 |",
        "|---|---|",
        f"| gold value 命中率 | {summary['value_hit_rate']:.4f} |",
        f"| 平均抽取事实数 | {summary['avg_facts']} |",
        f"| JSON 解析失败 | {summary['parse_fail']} / {summary['n']} |",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
