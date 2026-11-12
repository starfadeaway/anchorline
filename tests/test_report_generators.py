# -*- coding: utf-8 -*-
"""U7：报告生成器脚本不得把结论数字写死在模板里。"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_value_sentence_uses_numbers():
    cm = _load("compare_minimax")
    s = cm.value_sentence(67, 70, 72, 4)
    assert "67/72" in s and "70/72" in s and "4 道" in s
    assert "68/72" not in s  # 旧写死值不得出现


def test_arbitration_sentence_computed():
    cm = _load("compare_minimax")
    fake = {
        "a": ("表述差异（语义等价）", "x"),
        "b": ("规则分歧：null vs No", "y"),
        "c": ("口径分歧：12 vs 10", "z"),
    }
    s = cm.arbitration_sentence(fake)
    assert "仲裁 3 项" in s
    assert "真分歧 2 题" in s and "`b`" in s and "`c`" in s
    assert "另 1 题" in s and "`a`" in s


def test_qf_sentence_uses_numbers():
    cm = _load("cross_model_compare")
    s = cm.qf_sentence(15, 16)
    assert "15/16 一致" in s
    assert "16/16" not in s


@pytest.mark.parametrize("rel", ["compare_minimax.py", "cross_model_compare.py"])
def test_source_has_no_stale_literals(rel):
    text = open(os.path.join(ROOT, "scripts", rel), encoding="utf-8").read()
    assert "68/72" not in text
    assert "71/72" not in text or rel != "compare_minimax.py"
    assert "16/16 一致" not in text
