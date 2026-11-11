# -*- coding: utf-8 -*-
"""V2 `llm_gotchas_checker` 的 judge 实现（移植官方逻辑 + 冻结 prompt）。

官方实现（`evaluation/qa_eval_metrics.py`）：
  - system：`_GOTCHAS_JUDGE_SYSTEM_PROMPT`
  - user：固定 rubric 模板（question / reference / model full response / model final answer）
  - 要求 judge 输出 JSON：{"label": 0|1, "reason": "..."}

本模块负责：
  - 冻结 prompt（`prompt_sha256()` 写进结果文件，防止 judge 宽松度漂移）；
  - 构造 messages；
  - 解析 label（宽松处理 markdown 代码块）。
"""
from __future__ import annotations

import hashlib
import json
import re

GOTCHAS_SYSTEM_PROMPT = (
    "You are a strict grader for gotchas-style insight questions. "
    "The reference answer describes the key insight(s). "
    "Grade 1 if the model response includes at least one correct insight point from the reference answer "
    "(paraphrase allowed), and does not contradict any reference point. "
    "If the model's direction is wrong, or it contains contradictions against any reference point, grade 0. "
    "If the model gives multiple points, partial coverage is enough for 1 as long as no contradictions appear."
)

# 模板用占位符，运行时填充；hash 只对模板（不含具体题面/答案）
GOTCHAS_USER_TEMPLATE = (
    "Evaluate whether the model answer captures the gotcha insight.\n\n"
    "Question:\n{question}\n\n"
    "Reference answer (insight points):\n{reference_answer}\n\n"
    "Model full response:\n{model_full_response}\n\n"
    "Model extracted final answer:\n{model_final_answer}\n\n"
    "Scoring rubric:\n"
    "- Label 1 if the model includes at least one correct insight point from the reference answer "
    "(paraphrase acceptable), and does not contradict any reference point.\n"
    "- Label 1 even if only part of a multi-point reference answer is covered, as long as there is "
    "no contradiction.\n"
    "- Label 0 if direction is wrong (suggests opposite action/cause), even if some wording overlaps.\n"
    "- Label 0 if any point in the model response contradicts any reference point.\n"
    "- Label 0 if the response is irrelevant or generic without insight.\n\n"
    "Output JSON only:\n"
    '{"label": 0 or 1, "reason": "short rationale"}'
)


def prompt_sha256() -> str:
    """冻结 prompt 的 sha256（system + 模板；不含题面/答案）。"""
    blob = (GOTCHAS_SYSTEM_PROMPT + "\n---\n" + GOTCHAS_USER_TEMPLATE).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def build_gotchas_messages(question: str, reference_answer: str, model_full_response: str, model_final_answer: str) -> list[dict]:
    # 用 replace 而不是 str.format：模板里含 JSON 示例的 {}，format 会当成占位符
    user = (
        GOTCHAS_USER_TEMPLATE
        .replace("{question}", question)
        .replace("{reference_answer}", reference_answer)
        .replace("{model_full_response}", model_full_response)
        .replace("{model_final_answer}", model_final_answer)
    )
    return [
        {"role": "system", "content": GOTCHAS_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def parse_binary_judgement(text: str) -> tuple[int, str] | None:
    """解析 judge 输出：JSON {label, reason}；失败返回 None。"""
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        payload = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    label = payload.get("label")
    if label in {0, 1, "0", "1"}:
        return int(label), str(payload.get("reason") or "")
    return None


def judge_gotchas(judge, question: str, reference_answer: str, answer: str, full_response: str | None = None) -> dict:
    """用 judge 客户端判一道 gotchas 题；返回 {label, reason, prompt_sha256}。

    judge 需有 `.complete(messages, max_tokens=...)` 方法（ChatClient）。
    """
    # full_response = 模型完整输出（含推理）；answer = 提取后的最终答案。当前调用方只有最终答案时两者相同。
    messages = build_gotchas_messages(question, reference_answer, full_response or answer, answer)
    text = judge.complete(messages, temperature=0.0, max_tokens=512)
    parsed = parse_binary_judgement(text)
    if parsed is None:
        return {"label": None, "reason": f"unparsable judge output: {text[:200]}", "prompt_sha256": prompt_sha256()}
    label, reason = parsed
    return {"label": label, "reason": reason, "prompt_sha256": prompt_sha256()}
