# -*- coding: utf-8 -*-
"""L0 行级去重的口径测试。

口径来源：dataset/v2/measure_compression.py（同一条轨迹内，行只保留首次出现）。
"""
from anchorline.memory.l0 import L0Deduper, lines_of


def test_lines_of_strips_and_drops_empty():
    assert lines_of("a\n\n b \n c") == ["a", "b", "c"]


def test_cross_state_dedupe_keeps_first_occurrence():
    d = L0Deduper()
    s0 = "nav\nitem A\nitem B"
    s1 = "nav\nitem A\nitem C"
    s2 = "nav\nitem C"
    assert d.feed(s0) == ["nav", "item A", "item B"]
    assert d.feed(s1) == ["item C"]
    assert d.feed(s2) == []
    assert d.stats.raw_lines == 8
    assert d.stats.novel_lines == 4


def test_feed_states_join_between_state_blocks():
    d = L0Deduper()
    out = d.feed_states(["a\nb", "b\nc", "c\nd"])
    assert out == "a\nb\n\nc\n\nd"


def test_empty_input_is_safe():
    d = L0Deduper()
    assert d.feed("") == []
    assert d.stats.compression == 0.0
    assert d.stats.dup_ratio == 0.0
