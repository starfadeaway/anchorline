# -*- coding: utf-8 -*-
"""gotchas judge 的单测（冻结 prompt / 解析 / 调用）。"""
from anchorline.evaluation.gotchas_judge import (
    GOTCHAS_SYSTEM_PROMPT,
    build_gotchas_messages,
    judge_gotchas,
    parse_binary_judgement,
    prompt_sha256,
)


class FakeJudge:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        return self.reply


def test_prompt_hash_is_stable_and_short():
    h = prompt_sha256()
    assert len(h) == 64
    assert h == prompt_sha256()


def test_messages_contain_question_and_reference():
    msgs = build_gotchas_messages("Q?", "Ref answer", "full resp", "final ans")
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == GOTCHAS_SYSTEM_PROMPT
    assert "Q?" in msgs[1]["content"]
    assert "Ref answer" in msgs[1]["content"]


def test_parse_binary_judgement():
    assert parse_binary_judgement('{"label": 1, "reason": "ok"}')[0] == 1
    assert parse_binary_judgement('```json\n{"label": 0, "reason": "no"}\n```')[0] == 0
    assert parse_binary_judgement('```json\n{"label": 1}\n```')[0] == 1
    assert parse_binary_judgement("not json") is None


def test_judge_gotchas_uses_frozen_hash():
    j = FakeJudge('{"label": 1, "reason": "matches"}')
    out = judge_gotchas(j, "Q", "Ref", "answer")
    assert out["label"] == 1
    assert out["prompt_sha256"] == prompt_sha256()
