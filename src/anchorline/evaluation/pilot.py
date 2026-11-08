# -*- coding: utf-8 -*-
"""评测 pilot 的公共抽样与数据加载。

aa_pilot（B 臂 A/A）与 eval_d_arm（D 臂）此前各写了一份「加载 V2 题 → 过滤 web →
排除 abs/judge 题 → seed 抽样」，这里统一，保证两个臂用**完全相同的 20 题**。
"""
from __future__ import annotations

import json
import os
import random

# evaluation/ -> anchorline/ -> src/ -> 仓库根
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2 = os.path.join(_ROOT, "dataset", "v2")


def load_v2_questions(path: str | None = None) -> dict[str, dict]:
    """读取 `questions.jsonl`，返回 {question_id: question}。"""
    path = path or os.path.join(V2, "questions.jsonl")
    qs: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                qs[q["id"]] = q
    return qs


def deterministic_web_questions(qs: dict[str, dict] | None = None) -> list[dict]:
    """web 域 + 确定性判分 + 非 abs 的题集（A/A pilot 的候选池，154 道）。"""
    from anchorline.evaluation.metrics import (
        LLM_JUDGE_FUNCS,
        parse_eval_function_spec,
    )

    qs = qs or load_v2_questions()
    out: list[dict] = []
    for q in qs.values():
        if not str(q.get("environment", "")).startswith("webarena"):
            continue
        if q["id"].endswith("_abs"):
            continue
        name, _ = parse_eval_function_spec(q["eval_function"])
        if name in LLM_JUDGE_FUNCS:
            continue
        if "abstention" in q["eval_function"]:
            continue
        out.append(q)
    return out


def sample_deterministic(limit: int = 20, seed: int = 42) -> list[dict]:
    """从确定性 web 题里按固定种子抽 limit 题（B/D 臂共用同一批）。"""
    pool = deterministic_web_questions()
    random.seed(seed)
    return random.sample(pool, min(limit, len(pool)))
