# -*- coding: utf-8 -*-
"""技能开关的存取（DB 表 skill_toggles）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from anchorline.models import SkillToggle
from anchorline.skills import BUILTIN_SKILLS, SKILL_BY_NAME, Skill


def list_skills(db: Session) -> list[tuple[Skill, bool]]:
    """内置技能 + 当前开关（未出现在表里的默认关闭）。"""
    rows = dict(db.execute(select(SkillToggle.name, SkillToggle.enabled)).all())
    return [(s, bool(rows.get(s.name, False))) for s in BUILTIN_SKILLS]


def set_skill(db: Session, name: str, enabled: bool) -> bool:
    """开/关一个技能；未知技能返回 False。"""
    if name not in SKILL_BY_NAME:
        return False
    row = db.get(SkillToggle, name)
    if row is None:
        db.add(SkillToggle(name=name, enabled=enabled))
    else:
        row.enabled = enabled
    db.commit()
    return True


def enabled_skills(db: Session) -> list[Skill]:
    return [s for s, on in list_skills(db) if on]
