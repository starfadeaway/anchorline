# -*- coding: utf-8 -*-
"""V1-KU 端到端问答评测（72 题）：给 reader 看 A/B 两个 gold session + 问题，判答案。

口径（与 V2 主集不同，V1 是冲突专项）：
- 1a（current，63 题）：答案是否命中 gold new_value（当前值）；命中 stale_value 记为「过期事实」；
- 1b（retrospective，9 题）：回溯题问旧值，答案是否命中 gold stale_value；
- 1c（abstention，6 题）：是否明确拒答（不知道/未提及/无法确认）。

输出：data/eval/v1_ku_eval.json + reports/v1_ku_eval.md
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
OUT_JSON = os.path.join(ROOT, "data", "eval", "v1_ku_eval.json")
OUT_MD = os.path.join(ROOT, "reports", "v1_ku_eval.md")

SYS = "你是记忆问答助手。只回答用户问的那一个事实，不要解释。"
PROMPT = """下面是用户的会话记录（A 较早，B 较晚）。请回答问题，只输出答案值本身（一个短词/数字/一句话）。

问题：{question}

会话 A（较早）：
{a}

会话 B（较晚）：
{b}

答案："""


def norm(x) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(x or "").lower()).strip()


def contains(haystack: str, needle: str) -> bool:
    h, n = norm(haystack), norm(needle)
    if not n:
        return False
    if n in h:
        return True
    # 数字/短值放宽：gold 的每个 token 都出现
    toks = [t for t in n.split() if len(t) >= 2]
    return bool(toks) and all(t in h for t in toks)


def parse_sessions(md: str) -> tuple[str, str]:
    a = b = ""
    m = re.search(r"## Session A.*?\n(.*?)(?=## Session B)", md, re.S)
    if m:
        a = m.group(1)
    m = re.search(r"## Session B.*?\n(.*)", md, re.S)
    if m:
        b = m.group(1)
    return a.strip(), b.strip()


def main() -> int:
    rows = [json.loads(line) for line in open(KU, encoding="utf-8") if line.strip()]
    client = reader_client(Settings())
    results = []
    for i, r in enumerate(rows, 1):
        qid = r["question_id"]
        md_path = os.path.join(MD_DIR, f"{qid}.md")
        if not os.path.exists(md_path):
            continue
        a, b = parse_sessions(open(md_path, encoding="utf-8").read())
        prompt = PROMPT.format(question=r.get("question") or "", a=a[:4000], b=b[:4000])
        try:
            answer = client.complete(
                [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2048,
            )
        except Exception:
            answer = ""
        qf = r.get("query_form") or "current"
        is_abs = bool(r.get("is_abstention"))
        new_v = r.get("new_value")
        stale_v = r.get("stale_value")
        if is_abs:
            hit = bool(re.search(r"不知道|未提及|没有|无法确认|不确定|无法回答", answer))
            kind = "abstention"
        elif qf == "retrospective":
            hit = contains(answer, stale_v or "")
            kind = "retrospective"
        else:
            hit = contains(answer, new_v or "")
            kind = "current"
        hit_stale = contains(answer, stale_v or "") if not is_abs else False
        results.append({
            "question_id": qid,
            "query_form": qf,
            "is_abstention": is_abs,
            "gold_new": new_v,
            "gold_stale": stale_v,
            "answer": answer.strip()[:300],
            "hit": hit,
            "hit_stale": hit_stale,
            "kind": kind,
        })
        print(f"  [{i}/{len(rows)}] {qid} {kind} hit={hit} stale={hit_stale} ans={answer.strip()[:40]!r}")

    def rate(rows_: list[dict]) -> float:
        return round(sum(1 for x in rows_ if x["hit"]) / len(rows_), 4) if rows_ else 0.0

    current = [x for x in results if x["kind"] == "current"]
    retro = [x for x in results if x["kind"] == "retrospective"]
    abst = [x for x in results if x["kind"] == "abstention"]
    summary = {
        "n": len(results),
        "n_current": len(current),
        "n_retrospective": len(retro),
        "n_abstention": len(abst),
        "current_hit_rate": rate(current),
        "retrospective_hit_rate": rate(retro),
        "abstention_hit_rate": rate(abst),
        "current_stale_rate": round(sum(1 for x in current if x["hit_stale"]) / len(current), 4) if current else 0.0,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, ensure_ascii=False, indent=1)

    lines = [
        "# V1-KU 端到端问答评测（72 题）\n",
        "> 口径：给 reader 看 A/B 两个 gold session + 问题；1a 看当前值命中、1b 看回溯旧值命中、1c 看拒答；",
        "> 与 V2 主集的 QA 准确率不是同一口径，不可直接比。reader deepseek-flash，temperature=0。\n",
        "| 层 | n | 命中率 |",
        "|---|---|---|",
        f"| 1a current（当前值） | {len(current)} | **{summary['current_hit_rate']:.4f}** |",
        f"| 1b retrospective（旧值） | {len(retro)} | **{summary['retrospective_hit_rate']:.4f}** |",
        f"| 1c abstention（拒答） | {len(abst)} | **{summary['abstention_hit_rate']:.4f}** |",
        "",
        f"- 1a 过期事实率（答到旧值）：**{summary['current_stale_rate']:.4f}**",
        "",
        "## 逐题（不一致）\n",
        "| qid | kind | gold_new | gold_stale | answer |",
        "|---|---|---|---|---|",
    ]
    for x in results:
        if not x["hit"]:
            lines.append(f"| `{x['question_id']}` | {x['kind']} | {x['gold_new']} | {x['gold_stale']} | {x['answer'][:60]} |")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
