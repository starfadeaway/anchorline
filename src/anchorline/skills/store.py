# -*- coding: utf-8 -*-
"""技能存取：内置（BUILTIN_SKILLS）+ 用户自定义（custom_skills 表）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from anchorline.models import CustomSkill, SkillToggle
from anchorline.skills import BUILTIN_SKILLS, SKILL_BY_NAME, Skill


def _custom_rows(db: Session) -> list[CustomSkill]:
    return list(db.scalars(select(CustomSkill).order_by(CustomSkill.created_at)))


def list_skills(db: Session) -> list[tuple[Skill, bool, str]]:
    """全部技能：[(Skill, enabled, source)]；内置在前，自定义在后。"""
    toggles = dict(db.execute(select(SkillToggle.name, SkillToggle.enabled)).all())
    out: list[tuple[Skill, bool, str]] = [
        (s, bool(toggles.get(s.name, False)), "builtin") for s in BUILTIN_SKILLS
    ]
    out.extend(
        (
            Skill(
                name=r.name,
                title=r.title,
                description=r.description or "",
                instructions=r.instructions,
                memory_entity=r.memory_entity,
                auto_activate=bool(r.auto_activate),
                trigger_keywords=r.trigger_keywords or "",
            ),
            bool(r.enabled),
            "custom",
        )
        for r in _custom_rows(db)
    )
    return out


def set_skill(db: Session, name: str, enabled: bool) -> bool:
    """开/关技能：内置写 skill_toggles，自定义写 custom_skills.enabled。"""
    if name in SKILL_BY_NAME:
        row = db.get(SkillToggle, name)
        if row is None:
            db.add(SkillToggle(name=name, enabled=enabled))
        else:
            row.enabled = enabled
    else:
        row = db.scalar(select(CustomSkill).where(CustomSkill.name == name))
        if row is None:
            return False
        row.enabled = enabled
    db.commit()
    return True


def create_custom(
    db: Session,
    name: str,
    title: str,
    description: str,
    instructions: str,
    memory_entity: str | None = None,
    auto_activate: bool = False,
    trigger_keywords: str = "",
) -> bool:
    """新建自定义技能；name 与内置/已有自定义冲突则失败。"""
    if name in SKILL_BY_NAME or db.scalar(select(CustomSkill).where(CustomSkill.name == name)) is not None:
        return False
    db.add(
        CustomSkill(
            name=name,
            title=title,
            description=description,
            instructions=instructions,
            enabled=True,
            memory_entity=memory_entity,
            auto_activate=auto_activate,
            trigger_keywords=trigger_keywords,
        )
    )
    db.commit()
    return True


def update_custom(
    db: Session,
    name: str,
    title: str | None,
    description: str | None,
    instructions: str | None,
    memory_entity: str | None = None,
    auto_activate: bool | None = None,
    trigger_keywords: str | None = None,
) -> bool:
    row = db.scalar(select(CustomSkill).where(CustomSkill.name == name))
    if row is None:
        return False
    if title is not None:
        row.title = title
    if description is not None:
        row.description = description
    if instructions is not None:
        row.instructions = instructions
    if memory_entity is not None:
        row.memory_entity = memory_entity or None
    if auto_activate is not None:
        row.auto_activate = auto_activate
    if trigger_keywords is not None:
        row.trigger_keywords = trigger_keywords
    db.commit()
    return True


def delete_custom(db: Session, name: str) -> bool:
    row = db.scalar(select(CustomSkill).where(CustomSkill.name == name))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def enabled_skills(db: Session) -> list[Skill]:
    return [s for s, on, _src in list_skills(db) if on]


def active_skills(db: Session, query: str) -> list[Skill]:
    """本轮的技能：手动开启的 + 自动激活（关键词命中）的。"""
    q = (query or "").lower()
    out: list[Skill] = []
    for s, on, _src in list_skills(db):
        kws = [k.strip().lower() for k in (s.trigger_keywords or "").split(",") if k.strip()]
        auto = bool(s.auto_activate and kws and any(k in q for k in kws))
        if on or auto:
            out.append(s)
    return out


def memory_context(db: Session, entity_id: str, limit: int = 10) -> list[str]:
    """技能绑定实体时，取该实体的当前事实（紧凑文本），用于注入。"""
    from sqlalchemy import select

    from anchorline.models import Fact

    rows = list(
        db.scalars(
            select(Fact)
            .where(Fact.entity_id == entity_id, Fact.valid_to.is_(None))
            .order_by(Fact.valid_from.desc())
            .limit(limit)
        )
    )
    return [f"{f.attribute} = {f.value}" for f in rows]


def memory_fact_count(db: Session, entity_id: str) -> int:
    from sqlalchemy import func, select

    from anchorline.models import Fact

    return int(
        db.scalar(select(func.count()).select_from(Fact).where(Fact.entity_id == entity_id, Fact.valid_to.is_(None))) or 0
    )
