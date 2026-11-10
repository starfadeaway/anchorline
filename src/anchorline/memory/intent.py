# -*- coding: utf-8 -*-
"""回溯意图识别（产品链路用，不是评测指标）。

- `classify_intent(question)`：判问题问的是 current（当前值）还是 retrospective（过去/最初的值）；
- 聊天入口会在用户问题为 retrospective 时注入系统提示，并要求 memory_search 带 include_history；
- 失败/超时默认 current（不阻塞聊天）。

与 M2 评测的关系：M2 测的是这个分类能力（98.6%）；这里把它接进产品。
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("anchorline.memory.intent")

PROMPT = """判断问题问的是「当前值」还是「过去/最初的值」。
只输出 JSON：{{"query_form": "current" 或 "retrospective"}}

问题：{question}
"""


def classify_intent(question: str, model: str = "deepseek") -> str:
    """返回 "current" 或 "retrospective"；任何异常都退化为 current。"""
    if not (question or "").strip():
        return "current"
    try:
        from anchorline.llm import chat_client

        out = chat_client(model).complete(
            [
                {"role": "system", "content": "你是问题意图分类器，只输出 JSON。"},
                {"role": "user", "content": PROMPT.format(question=question[:1000])},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return "current"
        parsed = json.loads(m.group(0))
        qf = str(parsed.get("query_form") or "").strip().lower()
        return "retrospective" if qf == "retrospective" else "current"
    except Exception:
        log.warning("intent classification failed; default current", exc_info=True)
        return "current"
