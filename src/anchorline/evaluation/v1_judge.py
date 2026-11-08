# -*- coding: utf-8 -*-
"""V1-KU 判定规则：回答是否使用了过期旧值 / 是否取到旧值。

三档匹配（协议 Step 4）：
  - exact：小写 + 去标点后，按 token 边界子串命中；
  - normalized：在 exact 基础上把英文数字词转阿拉伯数字、去货币符号与千分位；
  - fuzzy：token 级 F1 >= 阈值（默认 0.8；敏感性分析 0.7 / 0.8 / 0.9）。

用途：
  - 层 1a 过期事实率：judge_used_stale(pred, stale_value)
  - 层 1b 回溯一致率：judge_took_old(pred, stale_value)（retro 题的 stale_value 即官方旧值）
  - 层 1a 与协议一致率：由裁决结果与 expected_resolution 比较（M2 接裁决链后再做）
"""
from __future__ import annotations

import re

NUM_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40",
    "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
    "hundred": "100",
}

MODES = ("exact", "normalized", "fuzzy")


def normalize(text: object, *, digitize: bool = False) -> str:
    s = str(text or "").lower()
    s = s.replace("$", " ").replace(",", " ")
    s = re.sub(r"[^\w\s.]", " ", s)
    # 去掉非小数的句号（"Main St." -> "Main St"），保留 "1.5" 这类小数
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)
    if digitize:
        for word, num in NUM_WORDS.items():
            s = re.sub(rf"(?<!\w){word}(?!\w)", num, s)
    return " ".join(s.split())


def _contains(pred_norm: str, value_norm: str) -> bool:
    if not value_norm:
        return False
    return re.search(rf"(?<!\w){re.escape(value_norm)}(?!\w)", pred_norm) is not None


def token_f1(prediction: object, value: object) -> float:
    p = set(normalize(prediction, digitize=True).split())
    r = set(normalize(value, digitize=True).split())
    if not p or not r:
        return 0.0
    inter = len(p & r)
    if inter == 0:
        return 0.0
    precision = inter / len(p)
    recall = inter / len(r)
    return 2 * precision * recall / (precision + recall)


def match(prediction: object, value: object, *, mode: str = "normalized", fuzzy_threshold: float = 0.8) -> bool:
    if value is None:
        return False
    if mode == "exact":
        return _contains(normalize(prediction), normalize(value))
    if mode == "normalized":
        return _contains(normalize(prediction, digitize=True), normalize(value, digitize=True))
    if mode == "fuzzy":
        return token_f1(prediction, value) >= fuzzy_threshold
    raise ValueError(f"unknown mode: {mode}")


def judge_used_stale(
    prediction: str,
    record: dict,
    *,
    mode: str = "normalized",
    fuzzy_threshold: float = 0.8,
) -> dict:
    """层 1a：回答是否使用了 stale_value（过期事实）。

    跳过：stale_value 为 null（首次发生）、stale_value_is_placeholder=true（占位词）。
    """
    stale = record.get("stale_value")
    if stale is None:
        return {"skip": True, "reason": "no_stale_value"}
    if record.get("stale_value_is_placeholder"):
        return {"skip": True, "reason": "placeholder_stale"}
    hit = match(prediction, stale, mode=mode, fuzzy_threshold=fuzzy_threshold)
    return {"skip": False, "used_stale": hit, "stale_value": stale, "mode": mode, "f1": round(token_f1(prediction, stale), 3)}


def judge_took_old(
    prediction: str,
    record: dict,
    *,
    mode: str = "normalized",
    fuzzy_threshold: float = 0.8,
) -> dict:
    """层 1b：回溯题是否取到旧值（retro 题的 stale_value 即官方旧值）。"""
    old = record.get("stale_value")
    hit = match(prediction, old, mode=mode, fuzzy_threshold=fuzzy_threshold)
    return {"took_old": hit, "old_value": old, "mode": mode, "f1": round(token_f1(prediction, old), 3)}


CONCLUSION_TOKENS = {"yes", "no", "true", "false"}

# 值等价比较时忽略的停用词/功能词（代词、单位连接词）
VALUE_STOPWORDS = {
    "the", "a", "an", "my", "your", "his", "her", "their", "our",
    "per", "of", "on", "in", "at", "for", "with", "and", "or",
}


def content_tokens(text: object) -> set[str]:
    return {
        t for t in normalize(text, digitize=True).split()
        if t not in VALUE_STOPWORDS
    }


def value_equivalent(a: object, b: object) -> bool:
    """值等价（用于交叉标注比对与「同一事实」判定）：

    - 都为空 → True；一空一非空 → False；
    - 归一化后相等 → True；
    - 内容词集合有包含关系（"4 engineers" ⊃ "4"、"30 dozen" ⊃ "30"）→ True；
    - 否则 token F1 >= 0.8 → True。
    """
    if a is None or b is None:
        return a is None and b is None
    if normalize(a) == normalize(b):
        return True
    ca, cb = content_tokens(a), content_tokens(b)
    if not ca or not cb:
        return False
    if ca <= cb or cb <= ca:
        return True
    return token_f1(" ".join(sorted(ca)), " ".join(sorted(cb))) >= 0.8


def is_ambiguous_record(record: dict, *, threshold: float = 0.8) -> bool:
    """old/new 高度重叠（fuzzy F1 >= threshold）或共享结论词（Yes/No）的题：
    过期检测区分度弱，报告单列。"""
    stale = record.get("stale_value")
    new = record.get("new_value")
    if stale is None or not new:
        return False
    if token_f1(stale, new) >= threshold:
        return True
    stale_tokens = set(normalize(stale, digitize=True).split())
    new_tokens = set(normalize(new, digitize=True).split())
    return bool((stale_tokens & new_tokens) & CONCLUSION_TOKENS)
