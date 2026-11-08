# -*- coding: utf-8 -*-
"""L1 / L3 单测：确定性转换与预算组装。"""
from anchorline.memory.l1 import events_to_text, summarize_states
from anchorline.memory.l3 import ContextItem, assemble, estimate_tokens


def test_summarize_states_skips_empty_and_clips():
    states = [
        {"url": "http://x/a", "action": "click('1')", "thought": "  open  menu  "},
        {"url": "", "action": "", "thought": ""},
        "not-a-dict",
        {"url": "", "action": "", "thought": "only thought"},
    ]
    events = summarize_states(states)
    assert [e.index for e in events] == [0, 3]
    assert events[0].thought == "open menu"
    assert events[0].url == "http://x/a"
    text = events_to_text(events)
    assert text.count("\n") == 1


def test_estimate_tokens_is_floor_chars_over_4():
    assert estimate_tokens("abcdefgh") == 2
    assert estimate_tokens("abc") == 0


def test_assemble_respects_budget_and_keeps_order_by_score():
    items = [
        ContextItem(text="a" * 40, score=0.1),  # 11 tokens
        ContextItem(text="b" * 20, score=0.9),  # 6 tokens
        ContextItem(text="c" * 40, score=0.5),  # 11 tokens
    ]
    r = assemble(items, budget_tokens=20)
    # score 顺序 b(6) -> c(11) = 17，a 超预算
    assert [i.text[:1] for i in r.used_items] == ["b", "c"]
    assert r.used_tokens == 17
    assert [i.text[:1] for i in r.dropped_items] == ["a"]


def test_assemble_zero_budget_drops_everything():
    items = [ContextItem(text="x" * 40, score=1.0)]
    r = assemble(items, 0)
    assert r.text == ""
    assert r.used_tokens == 0
    assert len(r.dropped_items) == 1
