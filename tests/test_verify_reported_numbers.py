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
    # 第 31 轮：结论措辞护栏（check_conclusion_phrases）也会检查 README 与当前口径结论文档
    for rel in ("README.md", "docs/b_c1_c2_single_state_experiment.md"):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(v.os.path.join(v.ROOT, rel), dst)
    monkeypatch.setattr(v, "ROOT", str(tmp_path))
    monkeypatch.setattr(v, "EVAL", str(tmp_path / "data" / "eval"))
    monkeypatch.setattr(v, "BASELINE", str(tmp_path / "reports" / "reported_numbers.json"))
    return tmp_path


def _verify() -> int:
    return v.main()


def test_baseline_is_green(sandbox):
    assert _verify() == 0


def test_direction_flip_caught(sandbox):
    p = sandbox / "reports" / "m3_summary.md"
    text = p.read_text(encoding="utf-8")
    assert "−1.95pp" in text
    p.write_text(text.replace("−1.95pp", "+1.95pp", 1), encoding="utf-8")
    assert _verify() == 1


def test_gap_style_p_caught(sandbox):
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    old = "| C2 -> D | 0.5714 → 0.6623 | 154 | +0.0909 | 0.0488 |"
    assert old in text
    p.write_text(text.replace(old, old.replace("0.0488", "0.0336"), 1), encoding="utf-8")
    assert _verify() == 1


def test_row_level_binding_caught(sandbox):
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    old = "| C2 -> D | 0.5714 → 0.6623 | 154 | +0.0909 | 0.0488 |"
    assert old in text
    p.write_text(text.replace(old, old.replace("0.0488", "0.0336"), 1), encoding="utf-8")
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


def test_bare_pp_rounding_caught(sandbox):
    """J7：裸 pp 按书写位数精确匹配，3.2→3.3 不是舍入等价。"""
    p = sandbox / "reports" / "m3_summary.md"
    text = p.read_text(encoding="utf-8")
    old = "**+3.2pp（vs run2 的 B 53.9%，源 p=0.219；对比 B_run2_vs_C2（后者−前者））**"
    assert old in text
    p.write_text(text.replace(old, old.replace("+3.2pp", "+3.3pp"), 1), encoding="utf-8")
    assert _verify() == 1


def _annotated_c2_row() -> str:
    return "**+3.2pp（vs run2 的 B 53.9%，源 p=0.219；对比 B_run2_vs_C2（后者−前者））**"


def test_annotated_pp_symbol_flip_caught(sandbox):
    """第 26 轮洞 1：+3.2 → −3.2 必须被抓（旧实现 abs() 比较会放过）。"""
    p = sandbox / "reports" / "m3_summary.md"
    text = p.read_text(encoding="utf-8")
    old = _annotated_c2_row()
    assert old in text
    p.write_text(text.replace(old, old.replace("+3.2pp", "−3.2pp"), 1), encoding="utf-8")
    assert _verify() == 1


def test_annotated_pp_unknown_key_caught(sandbox):
    """第 26 轮洞 2：标注 key 不存在必须报错（旧实现静默跳过）。"""
    p = sandbox / "reports" / "m3_summary.md"
    text = p.read_text(encoding="utf-8")
    old = _annotated_c2_row()
    assert old in text
    p.write_text(text.replace(old, old.replace("B_run2_vs_C2", "B_run2_vs_ZZ"), 1), encoding="utf-8")
    assert _verify() == 1


def test_annotated_pp_missing_direction_caught(sandbox):
    """第 26 轮洞 3 的一半：标注缺方向必须报错（否则只能查绝对值）。"""
    p = sandbox / "reports" / "m3_summary.md"
    text = p.read_text(encoding="utf-8")
    old = _annotated_c2_row()
    assert old in text
    p.write_text(text.replace(old, old.replace("（后者−前者）", ""), 1), encoding="utf-8")
    assert _verify() == 1


def test_annotated_pp_direction_sign_matrix(sandbox):
    """第 27 轮：方向映射必须保留 diff 符号。

    D_run3_vs_D_neighbor 的 diff = +0.0195（D 更强）：
      前者−后者 = +1.95pp；后者−前者 = −1.95pp。
    """
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    cases = [
        ("1.95pp 对比 D_run3_vs_D_neighbor（前者−后者）", True),
        ("−1.95pp 对比 D_run3_vs_D_neighbor（前者−后者）", False),
        ("−1.95pp 对比 D_run3_vs_D_neighbor（后者−前者）", True),
        ("1.95pp 对比 D_run3_vs_D_neighbor（后者−前者）", False),
    ]
    for note, ok in cases:
        p.write_text(text.rstrip() + "\n\n> " + note + "\n", encoding="utf-8")
        ok_got = _verify() == 0
        assert ok_got == ok, f"{note}: expected ok={ok}, got ok={ok_got}"
    p.write_text(text, encoding="utf-8")
    assert _verify() == 0

# ---- 第 31 轮：结论措辞护栏的自检（防「移除调用/文件缺失/旧句残留」三类洞） ----


def test_conclusion_phrases_guard_registered():
    """移除 check_conclusion_phrases() 调用行必须被测试发现（护栏自身要有自检）。"""
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "verify_reported_numbers.py"), encoding="utf-8").read()
    assert "bad += check_conclusion_phrases()" in src


def test_conclusion_phrases_detects_missing(sandbox):
    """删掉必要措辞必须让 verify 变红。"""
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    assert "少赢 1 题" in text
    p.write_text(text.replace("少赢 1 题", "少赢 两 题", 1), encoding="utf-8")
    assert _verify() == 1


def test_conclusion_phrases_forbids_old_sentence(sandbox):
    """presence-only 绕过回归：旧措辞留在原地、别处塞新词也必须被抓。"""
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace("少赢 1 题", "少赢 1 题 部分来自 B 索引缺陷", 1), encoding="utf-8")
    assert _verify() == 1


def test_conclusion_phrases_missing_file_errors(sandbox):
    """文件缺失必须报错，不能静默 SKIP。"""
    (sandbox / "README.md").unlink()
    assert _verify() == 1

# ---- 第 32 轮：forbidden 变体（精确串漏洞） ----


def test_forbidden_variant_source(sandbox):
    """「部分源自 B 索引缺陷」也必须被抓（旧实现只匹配「来自」）。"""
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.rstrip() + "\n\n> 部分源自 B 索引缺陷。\n", encoding="utf-8")
    assert _verify() == 1


def test_forbidden_variant_spacing(sandbox):
    """去空格/多空格变体也要被抓。"""
    p = sandbox / "reports" / "m3_2x2.md"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.rstrip() + "\n\n> 部分   来自 B 索引缺陷。\n", encoding="utf-8")
    assert _verify() == 1


def test_forbidden_variant_on_readme(sandbox):
    """README 里「部分建立在 B 索引缺陷上；」旧句必须被抓，但带「且本身很脆弱」的限定句允许。"""
    p = sandbox / "README.md"
    text = p.read_text(encoding="utf-8")
    assert "且本身很脆弱" in text  # 对照组：当前限定句不触发
    p.write_text(text.rstrip() + "\n\n> 部分建立在 B 索引缺陷上；\n", encoding="utf-8")
    assert _verify() == 1
