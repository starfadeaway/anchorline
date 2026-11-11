# -*- coding: utf-8 -*-
"""O7/P3：assemble_blocks 预算/截断行为（每条测试都必须能区分新旧实现）。"""
from anchorline.memory.l3 import assemble_blocks


def test_truncation_has_marker_and_stays_within_budget():
    ctx, used, dropped = assemble_blocks([(1.0, "x" * 500)], budget_tokens=50)  # 200 chars
    assert len(ctx) <= 200
    assert ctx.endswith("…(截断)")
    assert used <= 50


def test_tiny_remaining_is_safe():
    """P3：194+100 时第二块只剩 4 字符 —— 旧实现会 201 超预算，新实现必须 ≤200。"""
    ctx, used, dropped = assemble_blocks([(1.0, "a" * 194), (0.9, "b" * 100)], budget_tokens=50)
    assert len(ctx) <= 200
    assert used <= 50


def test_separators_are_counted():
    """P3：两块 40+40 且预算 80 字符时，分隔符（2 字符）必须导致第二块被截断。"""
    ctx, used, dropped = assemble_blocks([(1.0, "a" * 40), (0.9, "b" * 40)], budget_tokens=20)  # 80 chars
    assert len(ctx) <= 80
    assert used <= 20
    assert ctx.endswith("…(截断)")  # 80 = 40 + 2 + 38 不足，第二块被截断


def test_empty_blocks_have_no_effect():
    ctx, used, dropped = assemble_blocks([], budget_tokens=50)
    assert ctx == "" and used == 0 and dropped == 0
    ctx2, used2, dropped2 = assemble_blocks([(1.0, "   ")], budget_tokens=50)
    assert ctx2 == "" and used2 == 0 and dropped2 == 0
