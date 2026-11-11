# -*- coding: utf-8 -*-
"""O7：assemble_blocks 预算/截断行为（此前零覆盖）。"""
from anchorline.memory.l3 import assemble_blocks


def test_truncation_has_marker_and_stays_within_budget():
    blocks = [(1.0, "x" * 500)]
    ctx, used, dropped = assemble_blocks(blocks, budget_tokens=50)  # 200 chars
    assert len(ctx) <= 200
    assert ctx.endswith("…(截断)")
    assert used <= 50


def test_tiny_remaining_does_not_overflow():
    """O6：剩余空间不足 6 字符时不能靠标记撑破预算。"""
    blocks = [(1.0, "a" * 199), (0.9, "b" * 100)]  # 第二块时剩余 1 字符
    ctx, used, dropped = assemble_blocks(blocks, budget_tokens=50)
    assert len(ctx) <= 200
    assert used <= 50


def test_separators_counted():
    blocks = [(1.0, "a" * 90), (0.9, "b" * 90)]
    ctx, used, dropped = assemble_blocks(blocks, budget_tokens=50)  # 200 chars
    assert len(ctx) <= 200
    assert ctx.count("\n\n") >= 1


def test_empty_blocks_dropped():
    ctx, used, dropped = assemble_blocks([], budget_tokens=50)
    assert ctx == "" and used == 0 and dropped == 0
