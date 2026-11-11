# -*- coding: utf-8 -*-
"""可开关技能：内置列表 / 开关持久化 / 注入语义。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.models import Base
from anchorline.skills import BUILTIN_SKILLS, SKILL_BY_NAME
from anchorline.skills.store import enabled_skills, list_skills, set_skill


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
    assert all(not on for _, on in list_skills(db))
    assert enabled_skills(db) == []


def test_toggle_persists(db):
    assert set_skill(db, "run_coach", True)
    assert [s.name for s in enabled_skills(db)] == ["run_coach"]
    assert set_skill(db, "run_coach", False)
    assert enabled_skills(db) == []


def test_unknown_skill_rejected(db):
    assert not set_skill(db, "no_such_skill", True)
    assert enabled_skills(db) == []
