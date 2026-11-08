# -*- coding: utf-8 -*-
"""V1 判定规则单测。"""
from anchorline.evaluation.v1_judge import (
    is_ambiguous_record,
    judge_took_old,
    judge_used_stale,
    match,
    normalize,
    token_f1,
)


def test_exact_vs_normalized_digit():
    assert match("four", "four", mode="exact")
    assert not match("4", "four", mode="exact")
    assert match("4", "four", mode="normalized")
    assert match("I have $400,000 approved", "$400,000", mode="normalized")


def test_token_boundary_no_false_positive():
    assert not match("I have 150 coins", "15", mode="exact")
    assert match("I have 15 coins", "15", mode="exact")


def test_fuzzy_threshold_sensitivity():
    pred = "Yes (four times a week vs three previously)"
    stale = "three times a week"
    f1 = token_f1(pred, stale)
    # 该题 F1≈0.667：0.6 档命中、0.7/0.9 档不命中——正是阈值敏感性要暴露的
    assert match(pred, stale, mode="fuzzy", fuzzy_threshold=0.6)
    assert not match(pred, stale, mode="fuzzy", fuzzy_threshold=0.7)
    assert not match(pred, stale, mode="fuzzy", fuzzy_threshold=0.9)
    assert 0.6 < f1 < 0.7


def test_judge_used_stale_skips_null_and_placeholder():
    assert judge_used_stale("anything", {"stale_value": None})["skip"] is True
    assert judge_used_stale("Old Company", {"stale_value": "Old Company", "stale_value_is_placeholder": True})["skip"] is True
    r = judge_used_stale("I still keep them under my bed", {"stale_value": "under my bed"})
    assert r["skip"] is False and r["used_stale"] is True


def test_judge_took_old_for_retrospective():
    rec = {"stale_value": "Premier Silver", "new_value": "Premier Gold"}
    assert judge_took_old("Previously you were Premier Silver", rec)["took_old"] is True
    assert judge_took_old("You are Premier Gold", rec)["took_old"] is False


def test_ambiguous_record_detected():
    rec = {"stale_value": "Yes (road bike only, before the new purchase)", "new_value": "Yes (road bike plus newly purchased hybrid bike)"}
    # F1≈0.4，但两者共享结论词 Yes → 按共享结论词判 ambiguous
    assert is_ambiguous_record(rec, threshold=0.8) is True


def test_ambiguous_record_not_triggered_by_plain_overlap():
    rec = {"stale_value": "under my bed", "new_value": "shoe rack in the closet"}
    assert is_ambiguous_record(rec) is False


def test_normalize_keeps_decimal():
    assert normalize("25:50") == "25 50"
    assert normalize("$420") == "420"
    assert normalize("Main St.") == "main st"
    assert normalize("1.5 hours") == "1.5 hours"


def test_value_equivalent_granularity():
    from anchorline.evaluation.v1_judge import value_equivalent

    assert value_equivalent("4 engineers", "4")
    assert value_equivalent("30 dozen", "30")
    assert value_equivalent("in the bedroom", "in my bedroom")
    assert value_equivalent("3 times per week", "three times a week")
    assert value_equivalent("Main St.", "the music shop on Main St")
    assert not value_equivalent("under my bed", "shoe rack in the closet")
    assert value_equivalent(None, None)
    assert not value_equivalent(None, "x")
