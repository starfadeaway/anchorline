# -*- coding: utf-8 -*-
"""G6：护栏自检——注入错误数字必须让 verify 变红（防止 SEG_PAT/检查器被改坏却无人发现）。"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import verify_reported_numbers as v


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    shutil.copytree(v.os.path.join(v.ROOT, "reports"), tmp_path / "reports")
    shutil.copytree(v.os.path.join(v.ROOT, "data", "eval"), tmp_path / "data" / "eval")
    monkeypatch.setattr(v, "ROOT", str(tmp_path))
    monkeypatch.setattr(v, "EVAL", str(tmp_path / "data" / "eval"))
    monkeypatch.setattr(v, "BASELINE", str(tmp_path / "reports" / "reported_numbers.json"))
    return tmp_path


def _verify() -> int:
    return v.main()


def test_baseline_is_green(sandbox):
    assert _verify() == 0


def test_direction_flip_caught(sandbox):
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    assert "**+10.39pp，p=0.0195**" in text
    p.write_text(text.replace("**+10.39pp，p=0.0195**", "**−10.39pp，p=0.0195**", 1), encoding="utf-8")
    assert _verify() == 1


def test_gap_style_p_caught(sandbox):
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    old = "D 66.23% vs B 57.14%（+9.09pp，p=0.0385）"
    assert old in text
    p.write_text(text.replace(old, "D 66.23% vs B 57.14%（+9.09pp，p=0.0336）", 1), encoding="utf-8")
    assert _verify() == 1


def test_row_level_binding_caught(sandbox):
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    old = "| C2 -> D | 0.5714 → 0.6623 | 154 | +0.0909 | 0.0336 |"
    assert old in text
    p.write_text(text.replace(old, old.replace("0.0336", "0.0385"), 1), encoding="utf-8")
    assert _verify() == 1


def test_six_digit_p_caught(sandbox):
    p = sandbox / "reports" / "d_arm_154_hybrid.md"
    text = p.read_text(encoding="utf-8")
    assert "0.019520" in text
    p.write_text(text.replace("0.019520", "0.099999", 1), encoding="utf-8")
    assert _verify() == 1


def test_hybrid_direction_caught(sandbox):
    p = sandbox / "reports" / "d_arm_154_hybrid.md"
    text = p.read_text(encoding="utf-8")
    assert "−10.39pp" in text
    p.write_text(text.replace("−10.39pp", "+10.39pp", 1), encoding="utf-8")
    assert _verify() == 1


def test_hybrid_diff_row_caught(sandbox):
    p = sandbox / "reports" / "d_arm_154_hybrid.md"
    text = p.read_text(encoding="utf-8")
    assert "**−0.1039**" in text
    p.write_text(text.replace("**−0.1039**", "**+0.1039**", 1), encoding="utf-8")
    assert _verify() == 1


def test_file_p_binding_caught(sandbox):
    p = sandbox / "reports" / "m3_d_intent.md"
    text = p.read_text(encoding="utf-8")
    assert "p=0.8145" in text
    p.write_text(text.replace("p=0.8145", "p=0.0195", 1), encoding="utf-8")
    assert _verify() == 1
