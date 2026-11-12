# -*- coding: utf-8 -*-
"""3-state 拼接切片的「按 State 分预算」（§42.2）。

背景：B/C1 的检索单元是 radius=1 的 3-state 拼接（median 49k / 40k 字符），保头截断
保住的是**最旧的 state**，center 状态（答案通常所在）在 27%–50% 处，大概率被整段丢掉。

本模块在**组装期**（不改索引）把 3-state 文本重新分配预算：
- 所有 State 的 header（State/URL/Action/AXTree 标记）**全保留**；
- AXTree 按 center 优先分配（center 50%，其余平分剩余 50%，可按 30/20 近似）；
- 总长不超过给定字符预算，截断处带「…(截断)」标记。

默认不启用（`answer_baseline(..., state_budget=True)` 或环境变量
`ANCHORLINE_STATE_BUDGET=1` 打开），需先做 A/B 验证效果再决定是否默认。
"""
from __future__ import annotations

import re

_STATE_RE = re.compile(r"(?m)^State (\d+) \(step (\d+)\)\s*$")
_AXTREE_MARK = "- AXTree:"
_MARK = "…(截断)"


def parse_states(text: str) -> list[dict]:
    """把 3-state 拼接文本拆成 [{index, header, tree}]；无法识别时返回单段。"""
    matches = list(_STATE_RE.finditer(text))
    if not matches:
        return [{"index": None, "header": "", "tree": text}]
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].rstrip("\n")
        pos = chunk.find(_AXTREE_MARK)
        if pos == -1:
            out.append({"index": int(m.group(1)), "header": chunk, "tree": ""})
        else:
            cut = pos + len(_AXTREE_MARK)
            out.append({"index": int(m.group(1)), "header": chunk[:cut], "tree": chunk[cut:].lstrip("\n")})
    return out


def _clip(tree: str, alloc: int) -> str:
    if alloc <= 0:
        return ""
    if len(tree) <= alloc:
        return tree
    if alloc <= len(_MARK):
        return _MARK[:alloc]
    return tree[: alloc - len(_MARK)] + _MARK


def budget_state_text(text: str, budget_chars: int, center: int | None = None) -> str:
    """按 State 重新分配预算；headers 全保留，center 的 AXTree 优先。"""
    if budget_chars <= 0 or len(text) <= budget_chars:
        return text
    states = parse_states(text)
    if len(states) == 1:
        return _clip(text, budget_chars)

    sep = "\n\n"
    headers = sum(len(s["header"]) for s in states) + len(sep) * (len(states) - 1)
    remain = budget_chars - headers
    if remain <= 0:
        # 连 header 都放不下：只保留 header，整体兜底截断
        joined = sep.join(s["header"] for s in states)
        return joined[:budget_chars]

    # center 优先：50% 给 center，其余均分剩余 50%；找不到 center 时均分
    center_idx = None
    if center is not None:
        center_idx = next((i for i, s in enumerate(states) if s["index"] == center), None)
    if center_idx is None:
        center_idx = len(states) // 2
        shares = [remain / len(states)] * len(states)
    else:
        others = len(states) - 1
        shares = [0.0] * len(states)
        shares[center_idx] = remain * 0.5
        rest = (remain * 0.5) / others if others else 0.0
        for i in range(len(states)):
            if i != center_idx:
                shares[i] = rest

    parts = []
    for s, share in zip(states, shares):
        parts.append(s["header"] + "\n" + _clip(s["tree"], int(share)))
    out = sep.join(parts)
    return out if len(out) <= budget_chars else out[:budget_chars]
