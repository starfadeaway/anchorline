# -*- coding: utf-8 -*-
"""技能（内置 + 自定义）：开关持久化 / 自定义 CRUD / 注入列表。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.memory.store import FactStore
from anchorline.models import Base, Fact
from anchorline.skills import BUILTIN_SKILLS, SKILL_BY_NAME
from anchorline.skills.store import (
    active_skills,
    create_custom,
    delete_custom,
    enabled_skills,
    list_skills,
    memory_context,
    memory_fact_count,
    set_skill,
    update_custom,
)


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
    assert len(custom) == 1 and custom[0][0].name == "my_skill" and custom[0][1] is True
    # 自定义默认开启 → 直接进入注入列表
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
