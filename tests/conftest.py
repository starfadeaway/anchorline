# -*- coding: utf-8 -*-
"""全局测试隔离：禁止单测触发真实 embedding/索引（L5：避免联网、随机红、额度消耗）。"""
import pytest


@pytest.fixture(autouse=True)
def _no_real_index(monkeypatch, request):
    # M6：需要真实索引的测试显式打 @pytest.mark.real_index，不再按文件名字符串豁免
    if request.node.get_closest_marker("real_index"):
        yield
        return
    try:
        from anchorline.retrieval import facts_index

        monkeypatch.setattr(facts_index, "upsert_fact", lambda *a, **k: None, raising=False)
        monkeypatch.setattr(facts_index, "delete_fact", lambda *a, **k: None, raising=False)
    except Exception:
        pass
    yield
