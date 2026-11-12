# -*- coding: utf-8 -*-
"""§42.2：3-state 切片的按 State 分预算（离线，不调 API）。"""

from anchorline.evaluation.state_budget import budget_state_text, parse_states

SAMPLE = """State 1 (step 1)
- URL: http://a/1
- Action: click
- AXTree:
L1-OLD """ + "x" * 2000 + """

State 2 (step 2)
- URL: http://a/2
- Action: type
- AXTree:
L2-CENTER """ + "c" * 4000 + """

State 3 (step 3)
- URL: http://a/3
- Action: click
- AXTree:
L3-OLD """ + "y" * 2000


def test_parse_states_splits_three():
    states = parse_states(SAMPLE)
    assert [s["index"] for s in states] == [1, 2, 3]
    assert "L2-CENTER" in states[1]["tree"]
    assert states[1]["header"].startswith("State 2 (step 2)")


def test_budget_keeps_all_headers_and_favors_center():
    out = budget_state_text(SAMPLE, budget_chars=3000, center=2)
    assert len(out) <= 3000
    # 三个 header 全保留
    for n in (1, 2, 3):
        assert f"State {n} (step {n})" in out
    # center 的 AXTree 保留得比两侧多
    states = parse_states(out)
    center_tree = states[1]["tree"]
    side_trees = [s["tree"] for i, s in enumerate(states) if i != 1]
    assert center_tree.count("c") > max(t.count("x") + t.count("y") for t in side_trees)
    assert "L2-CENTER" in center_tree


def test_budget_marks_truncated_states():
    out = budget_state_text(SAMPLE, budget_chars=1200, center=2)
    assert len(out) <= 1200
    assert "…(截断)" in out


def test_noop_when_within_budget():
    assert budget_state_text(SAMPLE, budget_chars=10_000, center=2) == SAMPLE


def test_single_state_clipped_to_budget():
    single = "State 0 (step 0)\n- AXTree:\n" + "z" * 500
    out = budget_state_text(single, budget_chars=100)
    assert len(out) <= 100
