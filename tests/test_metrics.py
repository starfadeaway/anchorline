# -*- coding: utf-8 -*-
"""V2 判分函数移植的单测（含 626e401e 的 `_` 归一化用例）。"""
from anchorline.evaluation.metrics import (
    extract_boxed_answer,
    mc_choice_match,
    mc_choice_set_match,
    norm_phrase_set_match,
    score_deterministic,
    split_phrases,
)


def test_relationship_advice_matches_two_phrases():
    spec = "norm_phrase_set_match|lower=true|normalize_hyphen=true|strip_punct=true|separators=,;|require_non_empty=true"
    assert score_deterministic("relationship_advice", "relationship, advice", spec) is True
    assert score_deterministic("worldnews", "relationship, advice", spec) is False


def test_split_phrases_keeps_order_and_drops_empty():
    assert split_phrases("a, b; c", separators=(",", ";")) == ["a", "b", "c"]


def test_boxed_extraction():
    assert extract_boxed_answer("blah \\boxed{Right Arrow} tail") == "Right Arrow"
    assert extract_boxed_answer("no box") == "no box"


def test_mc_choice_match_strips_choice_word():
    assert mc_choice_match("\\boxed{Choice B}", "b") is True
    assert mc_choice_match("\\boxed{A}", "b") is False


def test_mc_choice_set_match_order_insensitive():
    assert mc_choice_set_match("B, A", "A, B") is True
    assert mc_choice_set_match("A, B", "A, C") is False


def test_llm_judge_returns_none():
    assert score_deterministic("x", "y", "llm_gotchas_checker|require_non_empty=true") is None


def test_norm_phrase_set_match_requires_all_phrases():
    assert norm_phrase_set_match("relationship advice", "relationship, advice") is True
    assert norm_phrase_set_match("relationship only", "relationship, advice") is False
