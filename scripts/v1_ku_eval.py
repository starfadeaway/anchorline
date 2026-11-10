# -*- coding: utf-8 -*-
"""V1-KU 端到端问答评测（72 题，两段式 + LLM judge）。

两段式（修「回溯题全答当前值」）：
  1) 意图判定：给问题 + A/B 会话，判 current / retrospective（与 M2 同提示词）；
  2) 条件回答：按意图提示模型「回答当前值」或「回答旧值（A 段）」；
  3) 判定：LLM judge 判答案与期望值（current→new_value / retrospective→stale_value）是否等价。

对照模式（--mode single）：旧实现（单段、子串匹配），用于说明判定器差异。

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
from anchorline.llm import judge_client, reader_client  # noqa: E402

KU = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
MD_DIR = os.path.join(ROOT, "dataset", "v1", "minimax-package", "questions")
OUT_JSON = os.path.join(ROOT, "data", "eval", "v1_ku_eval.json")
OUT_MD = os.path.join(ROOT, "reports", "v1_ku_eval.md")

SYS_INTENT = "你是问题意图分类器，只输出 JSON。"
PROMPT_INTENT = """判断问题问的是「当前值」还是「过去/最初的值」。
只输出 JSON：{{"query_form": "current" 或 "retrospective"}}

问题：{question}

会话 A（较早）：
{a}

会话 B（较晚）：
{b}
"""

SYS_ANSWER = "你是记忆问答助手。只回答被问的那一个事实，不要解释。"
PROMPT_CURRENT = """下面是用户的会话记录（A 较早，B 较晚）。
问题问的是「当前值」——请根据会话回答当前状态，只输出答案值本身。

问题：{question}

会话 A（较早）：
{a}

会话 B（较晚）：
{b}

当前值："""

PROMPT_RETRO = """下面是用户的会话记录（A 较早，B 较晚）。
问题问的是「过去/最初的值」——请根据会话回答较早的状态（A 段），不要回答当前值，只输出答案值本身。

问题：{question}

会话 A（较早）：
{a}

会话 B（较晚）：
{b}

过去的值："""

SYS_JUDGE = "你是判定器，只输出 JSON。"
PROMPT_JUDGE = """问题：{question}
参考答案：{gold}
模型回答：{answer}

模型回答与参考答案是否等价（允许表述、单位、数字格式不同；只要指向同一个事实值即可）？
只输出 JSON：{{"equivalent": true 或 false}}
"""


def norm(x) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(x or "").lower()).strip()


def parse_sessions(md: str) -> tuple[str, str]:
    a = b = ""
    m = re.search(r"## Session A.*?\n(.*?)(?=## Session B)", md, re.S)
    if m:
        a = m.group(1)
    m = re.search(r"## Session B.*?\n(.*)", md, re.S)
    if m:
        b = m.group(1)
    return a.strip(), b.strip()


def extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def judge_equivalent(judge, question: str, gold: str, answer: str) -> bool:
    if not gold:
        return False
    try:
        out = judge.complete(
            [{"role": "system", "content": SYS_JUDGE},
             {"role": "user", "content": PROMPT_JUDGE.format(question=question, gold=gold, answer=answer)}],
            temperature=0.0,
            max_tokens=256,
        )
        parsed = extract_json(out) or {}
        return bool(parsed.get("equivalent"))
    except Exception:
        return False


def main() -> int:
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "two-stage"
    rows = [json.loads(line) for line in open(KU, encoding="utf-8") if line.strip()]
    reader = reader_client(Settings())
    judge = judge_client(Settings())

    results = []
    for i, r in enumerate(rows, 1):
        qid = r["question_id"]
        md_path = os.path.join(MD_DIR, f"{qid}.md")
        if not os.path.exists(md_path):
            continue
        a, b = parse_sessions(open(md_path, encoding="utf-8").read())
        question = r.get("question") or ""
        gold_qf = r.get("query_form") or "current"
        new_v, stale_v = r.get("new_value"), r.get("stale_value")

        if mode == "single":
            answer = reader.complete(
                [{"role": "system", "content": SYS_ANSWER},
                 {"role": "user", "content": PROMPT_CURRENT.format(question=question, a=a[:4000], b=b[:4000])}],
                temperature=0.0,
                max_tokens=2048,
            ).strip()
            pred_qf = gold_qf  # 单段不判意图，按 gold 判定（与旧实现一致）
            expected = stale_v if gold_qf == "retrospective" else new_v
            hit = bool(norm(expected) and norm(expected) in norm(answer))
        else:
            # 1) 意图判定
            intent_out = reader.complete(
                [{"role": "system", "content": SYS_INTENT},
                 {"role": "user", "content": PROMPT_INTENT.format(question=question, a=a[:3000], b=b[:3000])}],
                temperature=0.0,
                max_tokens=2048,
            )
            pred_qf = (extract_json(intent_out) or {}).get("query_form") or "current"
            if pred_qf not in ("current", "retrospective"):
                pred_qf = "current"
            # 2) 条件回答
            tmpl = PROMPT_RETRO if pred_qf == "retrospective" else PROMPT_CURRENT
            answer = reader.complete(
                [{"role": "system", "content": SYS_ANSWER},
                 {"role": "user", "content": tmpl.format(question=question, a=a[:4000], b=b[:4000])}],
                temperature=0.0,
                max_tokens=2048,
            ).strip()
            expected = stale_v if pred_qf == "retrospective" else new_v
            # 3) judge 判等价
            hit = judge_equivalent(judge, question, expected or "", answer)

        results.append({
            "question_id": qid,
            "query_form": gold_qf,
            "pred_query_form": pred_qf,
            "expected": expected,
            "answer": answer[:300],
            "hit": hit,
        })
        print(f"  [{i}/{len(rows)}] {qid} gold_qf={gold_qf} pred_qf={pred_qf} hit={hit} ans={answer[:40]!r}")

    def rate(rows_: list[dict]) -> float:
        return round(sum(1 for x in rows_ if x["hit"]) / len(rows_), 4) if rows_ else 0.0

    current = [x for x in results if x["query_form"] == "current"]
    retro = [x for x in results if x["query_form"] == "retrospective"]
    intent_acc = round(sum(1 for x in results if x["pred_query_form"] == x["query_form"]) / len(results), 4) if results else 0.0
    summary = {
        "mode": mode,
        "n": len(results),
        "n_current": len(current),
        "n_retrospective": len(retro),
        "intent_acc": intent_acc,
        "current_hit_rate": rate(current),
        "retrospective_hit_rate": rate(retro),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, ensure_ascii=False, indent=1)

    lines = [
        f"# V1-KU 端到端问答评测（72 题，{mode}）\n",
        "> 两段式：先判意图（current/retrospective）→ 按意图提示模型取当前值/旧值 → LLM judge 判等价。",
        "> 对照 single：单段提示 + 子串匹配（旧实现，下界）。与 V2 主集不是同一口径。\n",
        "| 指标 | 值 |",
        "|---|---|",
        f"| 意图判定准确率（对比 gold query_form） | {intent_acc:.4f} |",
        f"| 1a current 命中率（judge） | **{summary['current_hit_rate']:.4f}**（n={len(current)}） |",
        f"| 1b retrospective 命中率（judge） | **{summary['retrospective_hit_rate']:.4f}**（n={len(retro)}） |",
        "",
        "## 逐题未命中\n",
        "| qid | gold_qf | pred_qf | expected | answer |",
        "|---|---|---|---|---|",
    ]
    for x in results:
        if not x["hit"]:
            lines.append(f"| `{x['question_id']}` | {x['query_form']} | {x['pred_query_form']} | {x['expected']} | {x['answer'][:60]} |")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("written:", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
