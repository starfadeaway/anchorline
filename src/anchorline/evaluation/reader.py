# -*- coding: utf-8 -*-
"""官方 reader prompt 与消息构造（V2-web）。

来源：LongMemEval-V2 `evaluation/harness.py`（Apache-2.0）：
  - `DOMAIN_SYSTEM_PROMPTS["web"]`
  - `build_messages`：`### Memory context:` + context items + `### Question to answer:`
"""
from __future__ import annotations

WEB_SYSTEM_PROMPT = (
    "You are an experienced colleague in a web browsing environment that has "
    "a customized magento-based shopping website, a customized magento-based "
    "shopping admin cms website, as well as a customized forum website based "
    "on reddit/postmill. Answer based on your memory of the environment. "
    "If you do not know the answer, output exactly \\boxed{UNKNOWN}. "
    "Do not guess. Never attempt to guess an answer if you are not sure. "
    "If you believe the question's construction/premise is wrong, provide an "
    "explanation in \\boxed{} explaining why the question is flawed."
)


def build_messages(
    question: str,
    memory_context: str,
    *,
    system_prompt: str = WEB_SYSTEM_PROMPT,
) -> list[dict]:
    intro = "### Memory context:\n" + (memory_context.strip() or "(empty)")
    question_block = f"\n\n### Question to answer:\n{question}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": intro + question_block},
    ]
