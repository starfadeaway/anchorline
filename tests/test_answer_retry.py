# -*- coding: utf-8 -*-
"""硬校验测试：写入新值但回答未体现 → 自动重答。"""
import json

from anchorline.api.main import _verify_and_retry_answer


class FakeReader:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        return self.reply


def test_retries_when_answer_stale():
    out = {
        "messages": [
            {"role": "user", "content": "连胜六人"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "memory_write", "arguments": json.dumps({"value": "连胜六个对手"})}}
                ],
            },
            {"role": "assistant", "content": "厉害，五连胜说明你的正手已经够用。"},
        ]
    }
    reader = FakeReader("连胜六人，恭喜！")
    res = _verify_and_retry_answer(out, reader)
    assert res.get("answer_retry") is True
    assert reader.calls == 1
    assert "六" in res["messages"][-1]["content"]


def test_no_retry_when_answer_has_new_value():
    out = {
        "messages": [
            {"role": "user", "content": "连胜六人"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "memory_write", "arguments": json.dumps({"value": "连胜6个对手"})}}
                ],
            },
            {"role": "assistant", "content": "连胜 6 人，恭喜！"},
        ]
    }
    reader = FakeReader("不该被调用")
    res = _verify_and_retry_answer(out, reader)
    assert not res.get("answer_retry")
    assert reader.calls == 0


def test_no_retry_without_writes():
    out = {"messages": [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]}
    reader = FakeReader("不该被调用")
    res = _verify_and_retry_answer(out, reader)
    assert not res.get("answer_retry")
    assert reader.calls == 0
