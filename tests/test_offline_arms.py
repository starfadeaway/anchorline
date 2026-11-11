# -*- coding: utf-8 -*-
"""T10：评测链路的离线单测（不调任何外部 API）。"""
import os
import random

import pytest

from anchorline.evaluation import pilot
from anchorline.evaluation.reader import WEB_SYSTEM_PROMPT, build_messages


def test_build_messages_shape_and_content():
    msgs = build_messages("问题？", "### memory\n- a = 1")
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert msgs[0]["content"] == WEB_SYSTEM_PROMPT
    assert "问题？" in msgs[1]["content"] and "a = 1" in msgs[1]["content"]


def test_build_messages_empty_context():
    msgs = build_messages("q", "")
    assert "(empty)" in msgs[1]["content"]


@pytest.mark.skipif(
    not os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dataset", "v2", "questions.jsonl")),
    reason="dataset/ 未入库（fresh clone 无题池）",
)
def test_sample_deterministic_stable_and_no_global_rng_pollution():
    before = random.random()
    a = pilot.sample_deterministic(5, seed=42)
    b = pilot.sample_deterministic(5, seed=42)
    assert [x["id"] for x in a] == [x["id"] for x in b]  # 确定性
    # T13：抽样不得重置全局 RNG（同一随机序列在调用前后应可继续）
    random.seed(123)
    expected = random.random()
    random.seed(123)
    pilot.sample_deterministic(5, seed=42)
    assert random.random() == expected
    assert before != expected or True  # 仅记录，不做脆断言
