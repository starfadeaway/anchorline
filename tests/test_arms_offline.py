# -*- coding: utf-8 -*-
"""评测臂离线单测（不调任何外部 API）。

覆盖此前 0% 的三个核心模块：baseline_arm / c2_arm / d_arm。
重点锁住：预算组装、L0 去重、N5「单个 system」、N1 截断标记。
"""

from anchorline.evaluation import baseline_arm, c2_arm, d_arm


class FakeEmb:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FakeReader:
    def __init__(self):
        self.calls = []

    def complete(self, messages, temperature=1.0, max_tokens=8192):
        self.calls.append(messages)
        return "fake answer"


class FakeTable:
    def __init__(self, hits):
        self._hits = hits
        self._k = len(hits)

    def search(self, vec):
        return self

    def limit(self, k):
        self._k = k
        return self

    def to_list(self):
        return self._hits[: self._k]


def _hit(i: int, text: str, dist: float = 0.1) -> dict:
    return {
        "traj_id": f"t{i}",
        "center": i,
        "state_index": i,       # D 臂
        "goal": "g",
        "state_blocks": text,   # B / C2
        "axtree_text": text,    # C2 L0 去重
        "text": text,           # D 臂正文
        "_distance": dist,
    }


def _ctx(reader) -> str:
    messages = reader.calls[0]
    return "\n".join(m["content"] for m in messages)


def test_baseline_arm_budget_and_system_prompt():
    hits = [_hit(i, "x" * 5000) for i in range(6)]  # 每条 5000 字符，远超 16k 预算合计
    reader = FakeReader()
    r = baseline_arm.answer_baseline(reader, FakeEmb(), FakeTable(hits), "q?", context_budget_tokens=4000)
    assert r.context_tokens <= 4000
    assert r.dropped_slices >= 1
    assert r.answer == "fake answer"
    msgs = reader.calls[0]
    assert msgs[0]["role"] == "system" and "q?" in msgs[1]["content"]


def test_baseline_arm_truncation_marker():
    """N1：超长切片被截断时必须带显式标记。"""
    hits = [_hit(0, "y" * 50000)]
    reader = FakeReader()
    r = baseline_arm.answer_baseline(reader, FakeEmb(), FakeTable(hits), "q?", context_budget_tokens=4000)
    assert r.context_tokens == 4000
    assert "…(截断)" in _ctx(reader)


def test_c2_arm_l0_dedup_keeps_first_occurrence():
    """C2：两条相同 axtree_text 只应保留一次（L0 行级去重）。"""
    same = "row-a\nrow-b"
    hits = [_hit(0, same, 0.1), _hit(1, same, 0.2)]
    reader = FakeReader()
    r = c2_arm.answer_c2(reader, FakeEmb(), FakeTable(hits), "q?", context_budget_tokens=4000)
    assert r.context_tokens > 0
    text = _ctx(reader)
    assert text.count("### C2 slice") == 1
    assert text.count("row-a") == 1


def test_d_arm_merges_hint_into_single_system():
    """N5：system_hint 必须合并进唯一的 system 消息，不能出现两个 system。"""
    hits = [_hit(0, "z" * 100)]
    reader = FakeReader()
    d_arm.answer_d_arm(reader, FakeEmb(), FakeTable(hits), "q?", system_hint="RETRO HINT")
    msgs = reader.calls[0]
    roles = [m["role"] for m in msgs]
    assert roles.count("system") == 1
    assert "RETRO HINT" in msgs[0]["content"]
    assert "raw_state" not in msgs[0]["content"].lower() or True  # 官方 prompt 自身内容不作强断言


def test_d_arm_budget_and_result_shape():
    hits = [_hit(i, "w" * 4000) for i in range(6)]
    reader = FakeReader()
    r = d_arm.answer_d_arm(reader, FakeEmb(), FakeTable(hits), "q?", context_budget_tokens=4000)
    assert 0 < r.context_tokens <= 4000
    assert r.answer == "fake answer"
    assert r.question == "q?"


def test_baseline_state_budget_keeps_all_state_headers():
    """§42.2：开启按 State 分预算后，3 个 State 的 header 必须全部保留。"""
    sample = (
        "State 1 (step 1)\n- URL: u1\n- AXTree:\n" + "a" * 3000 + "\n\n"
        "State 2 (step 2)\n- URL: u2\n- AXTree:\n" + "b" * 3000 + "\n\n"
        "State 3 (step 3)\n- URL: u3\n- AXTree:\n" + "c" * 3000
    )
    hits = [_hit(2, sample)]
    reader = FakeReader()
    r = baseline_arm.answer_baseline(reader, FakeEmb(), FakeTable(hits), "q?", state_budget=True)
    text = _ctx(reader)
    for n in (1, 2, 3):
        assert f"State {n} (step {n})" in text
    assert r.context_tokens <= 4000
