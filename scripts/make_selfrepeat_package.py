# -*- coding: utf-8 -*-
"""生成 V1 自重复标注包（16 题）：分歧 4 + current 9 + retrospective 2 + abstention 1。

供给另一个标注者（MiniMax agent）在 48h 后盲标，用于测标注协议的一致性；
包内**不含第一次标注结果**，只含题、官方答案、会话原文。

用法：.venv\\Scripts\\python.exe scripts\\make_selfrepeat_package.py
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KU = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
SRC_MD = os.path.join(ROOT, "dataset", "v1", "minimax-package", "questions")
OUT = os.path.join(ROOT, "dataset", "v1", "selfrepeat-package")

DISPUTED = ["b01defab", "5831f84d", "d7c942c3", "89941a94"]


def md_question(path: str) -> str:
    text = open(path, encoding="utf-8").read()
    m = re.search(r"\*\*Question\*\*:\s*(.+)", text)
    return (m.group(1).strip() if m else "")


def md_official(path: str) -> str:
    text = open(path, encoding="utf-8").read()
    m = re.search(r"\*\*Official answer\*\*:\s*(.+)", text)
    return (m.group(1).strip() if m else "")


def main() -> int:
    rows = {r["question_id"]: r for r in (json.loads(line) for line in open(KU, encoding="utf-8") if line.strip())}
    current = [q for q, r in rows.items() if r.get("query_form") == "current" and not r.get("is_abstention")]
    retro = [q for q, r in rows.items() if r.get("query_form") == "retrospective"]
    abst = [q for q, r in rows.items() if r.get("is_abstention")]

    missing = [q for q in DISPUTED if q not in rows]
    if missing:
        raise SystemExit(f"disputed ids not in ku72: {missing}")

    random.seed(7)
    extra_current = [q for q in random.sample(current, len(current)) if q not in DISPUTED][:9]
    picked = list(dict.fromkeys(DISPUTED + extra_current + retro[:2] + abst[:1]))
    # 分歧题可能与分层重叠：补足 16 题
    for q in current:
        if len(picked) >= 16:
            break
        if q not in picked:
            picked.append(q)
    random.shuffle(picked)  # 打乱顺序，避免按 id 推断层

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "questions"), exist_ok=True)

    questions = []
    template = []
    for qid in picked:
        src = os.path.join(SRC_MD, f"{qid}.md")
        if not os.path.exists(src):
            raise SystemExit(f"missing md: {qid}")
        shutil.copy(src, os.path.join(OUT, "questions", f"{qid}.md"))
        question = md_question(src)
        official = md_official(src)
        questions.append({"question_id": qid, "question": question})
        template.append({
            "question_id": qid,
            "query_form": "",
            "new_value": "",
            "official_answer": official,
            "official_answer_role": "",
            "official_answer_session_index": "",
            "stale_value": "",
            "stale_value_is_placeholder": "",
            "stale_source_session_id": "",
            "new_source_session_id": "",
            "session_order_source": "manual",
            "gold_session_index": "",
            "is_abstention": False,
            "conflict_type": "",
            "expected_resolution": "",
            "entity": "",
            "match_mode": "",
            "note": "",
        })

    with open(os.path.join(OUT, "questions.jsonl"), "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    with open(os.path.join(OUT, "template.jsonl"), "w", encoding="utf-8") as f:
        for t in template:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(
            "# V1 自重复盲标包（16 题）\n\n"
            "用于「同一标注者 48h 后重标」的一致性检验。**禁止查看** `dataset/v1/minimax-package/annotations-minimax.jsonl`、"
            "`data/annotations/ku72.jsonl` 或任何第一次标注结果。\n\n"
            "## 任务\n"
            "对 `questions/` 下 16 个会话文件，按 `annotation-spec.md`（v3.2）输出标注，填入 `template.jsonl`：\n"
            "- query_form：current / retrospective；\n"
            "- new_value：当前值（retrospective 题为旧值，取官方答案语义）；\n"
            "- official_answer_role / official_answer_session_index：官方答案在 A/B 中的角色；\n"
            "- stale_value：被替代的旧值；没有则 null；占位符标注 stale_value_is_placeholder=true；\n"
            "- stale_source_session_id / new_source_session_id：旧值/新值所在 session；\n"
            "- gold_session_index：当前值所在 session（0=A，1=B）；\n"
            "- is_abstention：无法从会话确定答案时为 true；\n"
            "- conflict_type：时效 / 数值 / 否定 / 无；expected_resolution：覆盖 / 并存 / 无法裁决；\n"
            "- entity / match_mode / note 可留空或简述。\n\n"
            "## 判新旧只看 A/B 顺序，不用日期；retrospective 题的官方 answer 是旧值。\n\n"
            "## 输出\n"
            "把填好的 16 行 JSONL 写到 `selfrepeat-minimax.jsonl`（同目录），不要改动 template 的 question_id 顺序。\n"
        )

    with open(os.path.join(OUT, "监工清单.md"), "w", encoding="utf-8") as f:
        f.write(
            "# 监工清单（自重复 16 题）\n\n"
            "1. 确认标注者**没有**打开第一次结果（`annotations-minimax.jsonl` / `ku72.jsonl`）。\n"
            "2. 检查 16 行是否齐全、question_id 与 template 一致、没有多写/漏写。\n"
            "3. 抽查 4 题：\n"
            "   - 逐题对照会话原文，看 gold_session_index 与 new_source_session_id 是否指向同一 session；\n"
            "   - retrospective 题：new_value 是否等于**旧值**（官方 answer 语义）；\n"
            "   - abstention 题：is_abstention 是否为 true。\n"
            "4. 口径：自重复一致率 = 与第一次 `ku72.jsonl` 的字段一致率（query_form / new_value / gold_session_index 三项最重要）。\n"
            "5. 不一致时不要当场改；记录差异，交人工仲裁后再决定是否修正协议。\n"
        )

    print(f"written {len(picked)} cases -> {OUT}")
    print("order:", picked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
