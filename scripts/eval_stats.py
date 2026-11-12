# -*- coding: utf-8 -*-
"""确定性配对统计：精确符号翻转置换检验（不依赖 numpy 版本）。

配对差先精确转为 Fraction，再乘公共分母变成整数，用动态规划枚举
「每个差等概率取 ±d」的精确分布，从而得到与随机数/库版本无关的 p 值。
"""
from __future__ import annotations

import math
from fractions import Fraction


def sign_flip_exact(diffs: list[float | Fraction]) -> float:
    """精确双侧符号翻转 p 值：P(|Σ ±d_i| >= |Σ d_i|)。diffs 为配对差。"""
    if not diffs:
        return 1.0
    fr = [d if isinstance(d, Fraction) else Fraction(d).limit_denominator(max(1000, len(diffs))) for d in diffs]
    # U16：limit_denominator(1000) 是显式近似；n=154 时精确（分母 ≤154），n>1000 会失真
    denom = 1
    for f in fr:
        denom = math.lcm(denom, f.denominator)
    ints = [int(f * denom) for f in fr]
    obs = abs(sum(ints))
    if obs == 0:
        return 1.0
    counts: dict[int, int] = {0: 1}
    for x in ints:
        nxt: dict[int, int] = {}
        for s, c in counts.items():
            nxt[s + x] = nxt.get(s + x, 0) + c
            nxt[s - x] = nxt.get(s - x, 0) + c
        counts = nxt
    total = 2 ** len(ints)
    hit = sum(c for s, c in counts.items() if abs(s) >= obs)
    return hit / total


def paired_compare(a: dict[str, float], b: dict[str, float]) -> dict:
    """按共同 question_id 配对：返回 n、两臂均值、配对差均值、精确 p。"""
    common = sorted(set(a) & set(b))
    diffs = [a[q] - b[q] for q in common]
    n = len(common)
    mean_a = sum(a[q] for q in common) / n if n else 0.0
    mean_b = sum(b[q] for q in common) / n if n else 0.0
    return {
        "n": n,
        "accuracy_a": mean_a,
        "accuracy_b": mean_b,
        "diff_a_minus_b": (mean_a - mean_b) if n else 0.0,
        "p_exact": sign_flip_exact(diffs),
    }
