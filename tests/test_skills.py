# -*- coding: utf-8 -*-
"""技能（内置 + 自定义）：开关持久化 / 自定义 CRUD / 注入列表。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.memory.store import FactStore
from anchorline.models import Base, Fact
from anchorline.skills import BUILTIN_SKILLS, SKILL_BY_NAME
from anchorline.skills.context import ACTIVE_SKILLS
from anchorline.skills.store import (
    active_skills,
    build_skills_hint,
    create_custom,
    delete_custom,
    enabled_skills,
    list_skills,
    memory_context,
    memory_fact_count,
    set_skill,
    update_custom,
)
from anchorline.tools import build_tools


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_builtin_skills_are_unique():
    names = [s.name for s in BUILTIN_SKILLS]
    assert len(names) == len(set(names))
    assert "run_coach" in SKILL_BY_NAME


def test_default_all_disabled(db):
    assert all(not on for _, on, _src in list_skills(db))
    assert enabled_skills(db) == []


def test_toggle_builtin_persists(db):
    assert set_skill(db, "run_coach", True)
    assert [s.name for s in enabled_skills(db)] == ["run_coach"]
    assert set_skill(db, "run_coach", False)
    assert enabled_skills(db) == []


def test_custom_skill_crud(db):
    assert create_custom(db, "my_skill", "我的技能", "描述", "指令内容")
    skills = list_skills(db)
    custom = [(s, on, src) for s, on, src in skills if src == "custom"]
    assert len(custom) == 1 and custom[0][0].name == "my_skill" and custom[0][1] is False
    # C3：自定义技能默认关闭（与内置一致）
    assert enabled_skills(db) == []
    assert set_skill(db, "my_skill", True)
    assert [s.name for s in enabled_skills(db)] == ["my_skill"]
    # 更新内容
    assert update_custom(db, "my_skill", title="新标题", description=None, instructions="新指令")
    row = next(s for s, _, src in list_skills(db) if src == "custom")
    assert row.title == "新标题" and row.instructions == "新指令"
    # 关闭 + 删除
    assert set_skill(db, "my_skill", False)
    assert [s.name for s in enabled_skills(db)] == []
    assert delete_custom(db, "my_skill")
    assert not any(src == "custom" for _, _, src in list_skills(db))


def test_custom_name_conflicts(db):
    assert not create_custom(db, "run_coach", "x", "", "x")  # 与内置冲突
    assert create_custom(db, "dup", "a", "", "a")
    assert not create_custom(db, "dup", "b", "", "b")  # 与已有自定义冲突


def test_unknown_skill_rejected(db):
    assert not set_skill(db, "no_such_skill", True)
    assert not update_custom(db, "no_such_skill", "t", None, None)
    assert not delete_custom(db, "no_such_skill")


def test_skill_memory_binding(db):
    from datetime import datetime

    db.add(Fact(entity_id="user", attribute="5K PB", value="23:50", valid_from=datetime(2026, 1, 1), confidence=1.0))
    db.add(Fact(entity_id="user", attribute="饮食偏好", value="清淡", valid_from=datetime(2026, 1, 2), confidence=1.0))
    db.commit()
    assert create_custom(db, "run_coach_my", "我的教练", "", "指令", memory_entity="user")
    sk = next(s for s, _, src in list_skills(db) if src == "custom")
    assert sk.memory_entity == "user"
    assert memory_fact_count(db, "user") == 2
    ctx = memory_context(db, "user")
    assert any("5K PB" in c for c in ctx) and any("饮食偏好" in c for c in ctx)


def test_update_memory_entity(db):
    assert create_custom(db, "s1", "t", "", "i")
    assert update_custom(db, "s1", None, None, None, memory_entity="user.猫")
    assert next(s for s, _, src in list_skills(db) if src == "custom").memory_entity == "user.猫"
    assert update_custom(db, "s1", None, None, None, memory_entity="")
    assert next(s for s, _, src in list_skills(db) if src == "custom").memory_entity is None


def test_auto_activate_by_keywords(db):
    assert create_custom(db, "kb_auto", "KB", "", "i", auto_activate=True, trigger_keywords="原神,星铁")
    # 自定义技能默认开启；关掉后靠关键词自动激活
    assert set_skill(db, "kb_auto", False)
    assert [s.name for s in active_skills(db, "帮我查一下原神的角色")] == ["kb_auto"]
    assert active_skills(db, "今天天气怎么样") == []


def test_skill_name_recorded_in_fact(db):
    from datetime import datetime

    store = FactStore(db)
    f = store.write(entity_id="user", attribute="x", value="y", valid_from=datetime(2026, 1, 1), skill_name="run_coach")
    assert f.skill_name == "run_coach"


def test_build_skills_hint_injects_instructions(db):
    assert create_custom(db, "hint_skill", "t", "", "这是注入用的指令文本")
    assert build_skills_hint(db, []) == ""
    assert set_skill(db, "hint_skill", True)
    hint = build_skills_hint(db, enabled_skills(db))
    assert "这是注入用的指令文本" in hint and "[hint_skill]" in hint
    assert set_skill(db, "hint_skill", False)
    assert build_skills_hint(db, enabled_skills(db)) == ""

def test_memory_write_records_active_skill(db):
    """D6：走 build_tools 的真实写入路径，ACTIVE_SKILLS 必须落到 facts.skill_name。"""
    store = FactStore(db)
    tools = build_tools(store, "sess-1")
    token = ACTIVE_SKILLS.set(["run_coach"])
    try:
        res = tools["memory_write"](entity_id="user", attribute="5K PB", value="23:50")
    finally:
        ACTIVE_SKILLS.reset(token)
    assert res.ok
    fact = db.query(__import__("anchorline.models", fromlist=["Fact"]).Fact).first()
    assert fact.skill_name == "run_coach"


def test_memory_write_without_active_skill(db):
    store = FactStore(db)
    tools = build_tools(store, "sess-2")
    ACTIVE_SKILLS.set([])
    res = tools["memory_write"](entity_id="user", attribute="饮食偏好", value="清淡")
    assert res.ok
    fact = db.query(__import__("anchorline.models", fromlist=["Fact"]).Fact).first()
    assert fact.skill_name is None


def test_facts_endpoint_returns_skill_name(db):
    """E9：写→读贯通——/memory/facts 的响应模型必须带 skill_name。"""
    from anchorline.api.main import list_facts

    store = FactStore(db)
    tools = build_tools(store, "sess-read")
    token = ACTIVE_SKILLS.set(["run_coach"])
    try:
        tools["memory_write"](entity_id="user", attribute="5K PB", value="23:50")
    finally:
        ACTIVE_SKILLS.reset(token)

    rows = list_facts(limit=10, offset=0, db=db)
    assert rows and rows[0].skill_name == "run_coach"


def test_auto_activate_keyword_matrix(db):
    """E13/E14/E15：中文常见问法要触发、负向词不触发、单字关键词不再被删。"""
    assert create_custom(db, "diet_x", "饮食", "", "i", auto_activate=True, trigger_keywords="吃,吃什么,饮食")
    assert set_skill(db, "diet_x", False)
    assert [s.name for s in active_skills(db, "我今天吃什么比较好")] == ["diet_x"]
    assert [s.name for s in active_skills(db, "这家公司太会吃苦了")] == ["diet_x"]  # 单字「吃」保留（误伤属可接受）
    assert create_custom(db, "run_x", "跑步", "", "i", auto_activate=True, trigger_keywords="跑步,跑了")
    assert set_skill(db, "run_x", False)
    # run_coach 内置负向词只作用于内置技能；自定义 run_x 不受影响
    assert [s.name for s in active_skills(db, "我今天跑了 5 公里")] == ["run_x"]


def test_builtin_negative_keywords(db):
    """内置技能：跑步机 / 功能失效 不应自动激活。"""
    from anchorline.models import SkillToggle
    from anchorline.skills import SKILL_BY_NAME

    db.add(SkillToggle(name="run_coach", enabled=False, auto_activate=True, trigger_keywords=SKILL_BY_NAME["run_coach"].trigger_keywords))
    db.add(SkillToggle(name="memory_hygiene", enabled=False, auto_activate=True, trigger_keywords=SKILL_BY_NAME["memory_hygiene"].trigger_keywords))
    db.commit()
    assert [s.name for s in active_skills(db, "我在跑步机上走了 30 分钟")] == []
    assert [s.name for s in active_skills(db, "这个功能失效了")] == []
    assert "run_coach" in [s.name for s in active_skills(db, "我今天跑了 5 公里")]


def test_memory_context_truncation_marker(db):
    """E18：超长 value 截断且带标记。"""
    from datetime import datetime

    from anchorline.models import Fact

    db.add(Fact(entity_id="user", attribute="长文本", value="x" * 300, valid_from=datetime(2026, 1, 1), confidence=1.0))
    db.commit()
    ctx = memory_context(db, "user")
    assert any("…(截断)" in c for c in ctx)


def test_build_skills_hint_budget(db):
    """E18：总量预算生效（超预算的技能不注入）。"""
    assert create_custom(db, "big", "t", "", "y" * 200)
    assert set_skill(db, "big", True)
    sk = enabled_skills(db)
    hint = build_skills_hint(db, sk, budget=50)
    assert "未注入" in hint and "1 个技能" in hint  # L2/M4：全部超预算时只写数量


def test_builtin_negative_keywords_wired(db):
    """H3：内置技能定义里的 negative_keywords 必须经 list_skills 传出来（而不是永远走空/fallback）。"""
    from anchorline.skills.store import list_skills

    builtin = {s.name: s for s, _on, src in list_skills(db) if src == "builtin"}
    assert "跑步机" in builtin["run_coach"].negative_keywords
    assert "吃苦" in builtin["diet_plan"].negative_keywords


def test_negative_words_consumed(db):
    """I3：负向词必须走 active_skills 的过滤分支（而不仅是字段字符串）。"""
    from anchorline.models import SkillToggle
    from anchorline.skills import SKILL_BY_NAME

    db.add(
        SkillToggle(
            name="diet_plan",
            enabled=False,
            auto_activate=True,
            trigger_keywords=SKILL_BY_NAME["diet_plan"].trigger_keywords,
            negative_keywords=SKILL_BY_NAME["diet_plan"].negative_keywords,
        )
    )
    db.commit()
    assert [s.name for s in active_skills(db, "今天吃了苦")] == []
    assert [s.name for s in active_skills(db, "我吃了亏")] == []
    assert [s.name for s in active_skills(db, "我想吃苦瓜能减肥吗")] == ["diet_plan"]
    assert [s.name for s in active_skills(db, "今天吃什么")] == ["diet_plan"]
    # J8：手动开启 = 用户主动要，负向词只影响自动激活
    assert set_skill(db, "diet_plan", True)
    assert [s.name for s in active_skills(db, "今天吃了苦")] == ["diet_plan"]
    assert [s.name for s in active_skills(db, "今天吃什么")] == ["diet_plan"]


def test_negative_words_are_literal(db):
    """J1：负向词是用户输入，必须当字面匹配（不能执行正则，避免 ReDoS）。"""
    import time

    from anchorline.models import SkillToggle

    db.add(
        SkillToggle(
            name="diet_plan",
            enabled=False,
            auto_activate=True,
            trigger_keywords="吃",
            negative_keywords="(a+)+$",  # 恶意正则形态：必须被当作字面词
        )
    )
    db.commit()
    t0 = time.perf_counter()
    active_skills(db, "跑" + "a" * 30 + "!")
    assert time.perf_counter() - t0 < 0.5  # 若执行正则会指数级卡死


def test_negative_word_吃苦_range(db):
    """J5：连续字面「吃苦」也要被排除（此前测试没覆盖这条）。"""
    from anchorline.models import SkillToggle
    from anchorline.skills import SKILL_BY_NAME

    db.add(
        SkillToggle(
            name="diet_plan",
            enabled=False,
            auto_activate=True,
            trigger_keywords=SKILL_BY_NAME["diet_plan"].trigger_keywords,
            negative_keywords=SKILL_BY_NAME["diet_plan"].negative_keywords,
        )
    )
    db.commit()
    assert active_skills(db, "这家公司太会吃苦了") == []
    assert [s.name for s in active_skills(db, "我今天吃什么")] == ["diet_plan"]


def test_negative_keywords_three_state(db):
    """L1：NULL=用内置默认；只点开关不能清空负向词。"""
    from anchorline.models import SkillToggle
    from anchorline.skills import SKILL_BY_NAME

    row = SkillToggle(
        name="diet_plan",
        enabled=False,
        auto_activate=True,
        trigger_keywords=SKILL_BY_NAME["diet_plan"].trigger_keywords,
        negative_keywords=None,  # 用户没碰过负向词
    )
    db.add(row)
    db.commit()
    assert [s.name for s in active_skills(db, "今天吃了苦")] == []  # 内置负向词仍生效
    assert [s.name for s in active_skills(db, "今天吃什么")] == ["diet_plan"]
    # 显式清空后才能激活
    row.negative_keywords = ""
    db.commit()
    assert [s.name for s in active_skills(db, "今天吃了苦")] == ["diet_plan"]


def test_budget_note_truncated(db):
    """L2：全部丢弃时 note 也不能超预算。"""
    for i in range(5):
        create_custom(db, f"s{i}", "t", "", "x" * 60)
        set_skill(db, f"s{i}", True)
    hint = build_skills_hint(db, enabled_skills(db), budget=50)
    assert len(hint) <= 50
