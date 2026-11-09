# -*- coding: utf-8 -*-
"""判分器 boxed 提取的单测（对应诊断出的低分根因）。"""
from anchorline.evaluation.metrics import score_deterministic

SPEC = (
    "norm_phrase_set_match|lower=true|normalize_hyphen=true|strip_punct=true"
    "|separators=,;|require_non_empty=true"
)


def test_boxed_phrase_extracted():
    assert score_deterministic(r"\boxed{New Customers}", "New Customers", SPEC) is True
    assert score_deterministic(r"\boxed{\text{Submit}}", "Submit", SPEC) is True
    assert score_deterministic(r"\boxed{A}", "A", "mc_choice_match") is True
    assert score_deterministic(r"\boxed{true}", "true", "mc_choice_match") is True


def test_plain_answer_still_works():
    assert score_deterministic("Submit", "Submit", SPEC) is True
    assert score_deterministic("Something else", "Submit", SPEC) is False


def test_empty_prediction_fails():
    assert score_deterministic("", "Submit", SPEC) is False
