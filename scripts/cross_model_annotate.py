# -*- coding: utf-8 -*-
"""跨模型交叉标注（MiniMax）：独立标 16 题，与人类标注比对。

抽样：5 道争议题（89941a94 / c4ea545c / f685340e / 031748ae / 22d2cb42）
      + 11 道随机（seed=7），共 16 题。
材料：题面 + 官方 answer + 两个 gold session 全文（**不给人类标注**，盲标）。
输出：dataset/v1/cross-model-16.jsonl（原始模型输出 + 解析）
      dataset/v1/cross-model-16-compare.md（与人类标注的比对）
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from openai import OpenAI  # noqa: E402

from anchorline.config import Settings  # noqa: E402
from anchorline.evaluation.v1_judge import normalize  # noqa: E402

KU = os.path.join(ROOT, "dataset", "longmemeval_s_cleaned.json")
ANN = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
OUT_JSONL = os.path.join(ROOT, "dataset", "v1", "cross-model-16.jsonl")
OUT_MD = os.path.join(ROOT, "dataset", "v1", "cross-model-16-compare.md")

DISPUTED = ["89941a94", "c4ea545c", "f685340e", "031748ae", "22d2cb42"]

SYSTEM = """You are a careful data annotator for the LongMemEval-S knowledge-update benchmark.
You will get ONE question and its two gold sessions (the only sessions that matter).
Decide the annotation fields and return ONE JSON object, nothing else.

Definitions:
- query_form: "current" (asks the current state), "retrospective" (asks a previous/initial value; look for initially/previous/before/first N months), "abstention" (the question cannot be answered / premise wrong).
- new_value: the CURRENT value of the attribute (a concrete value, not a Yes/No conclusion and not a compound sentence).
- stale_value: the OLD value that was later superseded; use null if the fact did not exist before (first occurrence) or the old value is a placeholder.
- conflict_type: "时效" (temporal), "语义" (semantic), "偏好反转" (preference flip), or null.
- expected_resolution: "覆盖" (overwrite), "并存" (coexist), "标失效" (mark invalid), "升级人工" (escalate), or null.
- entity: the attribute being updated, in English.
- match_mode: "exact", "normalized", "fuzzy", or null.
- note: one short sentence.

Rules:
- Determine old vs new by the order of the two sessions in the provided concatenation (session A is earlier, session B is later). Do NOT use dates.
- For retrospective questions the official answer is the OLD value; the current value appears in the later session.
- Compound / two-slot questions that ask BOTH the previous and the current value (e.g. "when I just started ...? and now?"): set query_form="current" (the question ultimately asks the current state), put the concrete current value in new_value and the concrete old value in stale_value.
- For composite official answers (Yes/No conclusion, or "Previously..., Currently..."): put the concrete CURRENT value in new_value and the concrete OLD value in stale_value; do not copy the compound sentence.
- If you cannot determine a value, use null and explain in note.
- Keep your internal reasoning short (under ~150 words). If the question is ambiguous, still output the best JSON immediately after.
Return JSON only, with exactly these keys."""


def extract_json(text: str) -> dict | None:
    # MiniMax-M3 会把思考写进 <think>...</think>，先剥离，避免把思考里的 {} 当结果
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = [m.group(1)] if m else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    return None


def msg_lines(session) -> str:
    out = []
    for m in session or []:
        out.append(f"[{m.get('role')}] {str(m.get('content','')).strip()}")
    return "\n\n".join(out)


def main() -> int:
    ku = json.load(open(KU, encoding="utf-8"))
    qs = {q["question_id"]: q for q in ku if q.get("question_type") == "knowledge-update"}
    rows = [json.loads(l) for l in open(ANN, encoding="utf-8") if l.strip()]
    by_id = {r["question_id"]: r for r in rows}

    random.seed(7)
    pool = [r["question_id"] for r in rows if r["question_id"] not in DISPUTED]
    sample = DISPUTED + random.sample(pool, 16 - len(DISPUTED))
    print("sample:", sample)

    # 统一走 Settings（.env）：key 不在此处明文读取、不打印
    s = Settings()
    client = OpenAI(base_url=s.minimax_base_url, api_key=s.minimax_api_key)
    model = s.minimax_model

    results = []
    t0 = time.time()
    for n, qid in enumerate(sample, 1):
        q = qs[qid]
        sess = q["haystack_sessions"]
        sid = q["haystack_session_ids"]
        gold = sorted(q.get("answer_session_ids") or [], key=lambda s: sid.index(s))
        blocks = []
        for label, s in zip(("A (earlier)", "B (later)"), gold):
            i = sid.index(s)
            blocks.append(f"=== Session {label}: {s} (index {i}) ===\n{msg_lines(sess[i])}")
        user = (
            f"Question: {q['question']}\n"
            f"Official answer: {q.get('answer')}\n\n"
            + "\n\n".join(blocks)
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                temperature=0.0,
                max_tokens=8192,
            )
            raw = resp.choices[0].message.content or ""
            parsed = extract_json(raw)
        except Exception as exc:
            raw, parsed = f"ERROR: {exc}", None
        human = by_id[qid]
        rec = {
            "question_id": qid,
            "model": model,
            "raw": raw[:6000],
            "parsed": parsed,
            "human": {k: human.get(k) for k in ("query_form", "new_value", "stale_value", "conflict_type", "expected_resolution", "entity", "match_mode")},
        }
        results.append(rec)
        print(f"  [{n}/16] {qid} parsed={parsed is not None} {time.time()-t0:.0f}s")

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 比对：严格字符串 + 归一化/模糊（token F1>=0.8 视为语义一致）
    from anchorline.evaluation.v1_judge import token_f1

    def same(a, b) -> bool:
        if normalize(a) == normalize(b):
            return True
        if a is None or b is None:
            return False
        return token_f1(a, b) >= 0.8

    qf_ok = sv_ok = nv_ok = valid = 0
    qf_ok_n = sv_ok_n = nv_ok_n = 0
    for r in results:
        p = r["parsed"]
        if not p:
            continue
        valid += 1
        h = r["human"]
        if p.get("query_form") == h.get("query_form"):
            qf_ok += 1
        if normalize(p.get("stale_value")) == normalize(h.get("stale_value")):
            sv_ok += 1
        if normalize(p.get("new_value")) == normalize(h.get("new_value")):
            nv_ok += 1
        if p.get("query_form") == h.get("query_form"):
            qf_ok_n += 1
        if same(p.get("stale_value"), h.get("stale_value")):
            sv_ok_n += 1
        if same(p.get("new_value"), h.get("new_value")):
            nv_ok_n += 1
    lines = [
        "# 跨模型交叉标注（MiniMax）vs 人类标注\n",
        f"- 模型：`{model}`；样本：16 题（5 争议 + 11 随机 seed=7）",
        f"- 可解析输出：{valid}/16",
        f"- `query_form` 一致：{qf_ok}/{valid}",
        f"- `stale_value` 严格一致：{sv_ok}/{valid}；归一化/模糊一致：{sv_ok_n}/{valid}",
        f"- `new_value` 严格一致：{nv_ok}/{valid}；归一化/模糊一致：{nv_ok_n}/{valid}\n",
        "> 严格一致为字符串归一化相等；归一化/模糊一致额外允许数字词/单位差异与 token F1≥0.8。",
        "> 一致率是机器交叉检查，**不是第二人类标注者**；报告措辞不得写「双人标注」。\n",
        "## 逐题\n",
        "| qid | 模型 query_form | 人类 query_form | 模型 stale | 人类 stale | 模型 new | 人类 new | 语义一致 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        p = r["parsed"] or {}
        h = r["human"]
        agree = same(p.get("stale_value"), h.get("stale_value")) and same(p.get("new_value"), h.get("new_value")) and p.get("query_form") == h.get("query_form")
        lines.append(
            f"| `{r['question_id']}` | {p.get('query_form')} | {h.get('query_form')} | {p.get('stale_value')} | {h.get('stale_value')} | {p.get('new_value')} | {h.get('new_value')} | {'✅' if agree else '❌'} |"
        )
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"query_form一致 {qf_ok}/{valid} | stale严格 {sv_ok}/{valid} / 归一 {sv_ok_n}/{valid} | new严格 {nv_ok}/{valid} / 归一 {nv_ok_n}/{valid}")
    print("written:", OUT_JSONL, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
