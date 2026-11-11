# -*- coding: utf-8 -*-
"""技能存取：内置（BUILTIN_SKILLS）+ 用户自定义（custom_skills 表）。"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from anchorline.models import CustomSkill, SkillToggle
from anchorline.skills import BUILTIN_SKILLS, SKILL_BY_NAME, Skill

log = logging.getLogger("anchorline.skills")


def _custom_rows(db: Session) -> list[CustomSkill]:
    return list(db.scalars(select(CustomSkill).order_by(CustomSkill.created_at)))


def list_skills(db: Session) -> list[tuple[Skill, bool, str]]:
    """全部技能：[(Skill, enabled, source)]；内置在前，自定义在后。"""
    toggle_rows = {r.name: r for r in db.scalars(select(SkillToggle))}
    out: list[tuple[Skill, bool, str]] = []
    for s in BUILTIN_SKILLS:
        row = toggle_rows.get(s.name)
        # 内置技能用 skill_toggles 里的覆盖绑定（memory_entity/auto/keywords）
        out.append(
            (
                Skill(
                    name=s.name,
                    title=s.title,
                    description=(row.description if row is not None and row.description else s.description),
                    instructions=(row.instructions if row is not None and row.instructions else s.instructions),
                    memory_entity=(row.memory_entity if row is not None else None) or s.memory_entity,
                    auto_activate=bool(row.auto_activate) if row is not None else s.auto_activate,
                    trigger_keywords=(row.trigger_keywords if row is not None and row.trigger_keywords else s.trigger_keywords),
                    negative_keywords=(s.negative_keywords if row is None or row.negative_keywords is None else row.negative_keywords),  # L1：NULL=默认，""=显式清空
                ),
                bool(row.enabled) if row is not None else False,
                "builtin",
            )
        )
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
                negative_keywords=r.negative_keywords or "",
            ),
            bool(r.enabled),
            "custom",
        )
        for r in _custom_rows(db)
    )
    return out


def set_skill(db: Session, name: str, enabled: bool, commit: bool = True) -> bool:
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
    if commit:
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
    negative_keywords: str = "",
    commit: bool = True,
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
            enabled=False,  # C3：与内置技能一致，默认关闭，由用户显式开启
            memory_entity=memory_entity,
            auto_activate=auto_activate,
            trigger_keywords=trigger_keywords,
            negative_keywords=negative_keywords,
        )
    )
    if commit:
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
    negative_keywords: str | None = None,
    commit: bool = True,
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
    if negative_keywords is not None:
        row.negative_keywords = negative_keywords
    if commit:
        db.commit()
    return True


def delete_custom(db: Session, name: str) -> bool:
    row = db.scalar(select(CustomSkill).where(CustomSkill.name == name))
    if row is None:
        return False
    db.delete(row)
    # C6：顺手清掉 skill_toggles 里的同名残留行，避免脏数据
    toggle = db.get(SkillToggle, name)
    if toggle is not None:
        db.delete(toggle)
    db.commit()
    return True


def enabled_skills(db: Session) -> list[Skill]:
    return [s for s, on, _src in list_skills(db) if on]


def set_builtin_binding(
    db: Session,
    name: str,
    memory_entity: str | None = None,
    auto_activate: bool | None = None,
    trigger_keywords: str | None = None,
    negative_keywords: str | None = None,
    description: str | None = None,
    instructions: str | None = None,
    commit: bool = True,
) -> bool:
    """内置技能的覆盖（绑定/关键词/描述/指令；不改内置定义本身）。"""
    if name not in SKILL_BY_NAME:
        return False
    row = db.get(SkillToggle, name)
    if row is None:
        row = SkillToggle(name=name, enabled=False)
        db.add(row)
    if memory_entity is not None:
        row.memory_entity = memory_entity or None
    if auto_activate is not None:
        row.auto_activate = auto_activate
    if trigger_keywords is not None:
        row.trigger_keywords = trigger_keywords
    if negative_keywords is not None:
        row.negative_keywords = negative_keywords
    if description is not None:
        row.description = description.strip() or None
    if instructions is not None:
        row.instructions = instructions.strip() or None
    if commit:
        db.commit()
    return True


_FOOD_SUFFIX = ("瓜", "菜", "粒", "叶", "子")


def _negative_hit(q: str, word: str) -> bool:
    """字面命中负向词；若其后紧跟食物类字（吃苦瓜/吃苦菜），视为合法饮食问法。"""
    start = 0
    while True:
        idx = q.find(word, start)
        if idx == -1:
            return False
        nxt = q[idx + len(word) : idx + len(word) + 1]
        if not (word.startswith("吃") and nxt in _FOOD_SUFFIX):
            return True
        start = idx + 1


def active_skills(db: Session, query: str, lorekeeper_enabled: bool | None = None) -> list[Skill]:
    """本轮的技能：手动开启的 + 自动激活（关键词命中）的。

    B2：kb_search 依赖 LoreKeeper；未启用时即使开关打开也不注入（否则指令要求引用页面标题、
    而检索永远返回空 → 幻觉诱导）。
    """
    if lorekeeper_enabled is None:
        try:
            from anchorline.config import Settings

            lorekeeper_enabled = bool(Settings().lorekeeper_enabled)
        except Exception:
            lorekeeper_enabled = False
    q = (query or "").lower()
    # E15/G9：负向词优先取技能定义（内置技能可配），自定义技能无此列时为空
    fallback_negative = {"run_coach": ["跑步机", "跑步鞋"], "memory_hygiene": ["功能失效", "链接失效"]}
    out: list[Skill] = []
    for s, on, _src in list_skills(db):
        if s.name == "kb_search" and not lorekeeper_enabled:
            continue
        kws = [k.strip().lower() for k in (s.trigger_keywords or "").split(",") if k.strip()]
        hit = bool(kws and any(k in q for k in kws))
        raw_negs = (s.negative_keywords or "").strip()
        if raw_negs:
            negs = [n.strip() for n in raw_negs.replace("|", ",").split(",") if n.strip()]
        else:
            negs = fallback_negative.get(s.name, [])
        # J1：负向词只做字面匹配（用户可编辑 → 绝不执行正则，避免 ReDoS）
        # J3：逗号分隔；"吃苦瓜/吃苦菜"这类食物词通过后缀排除，避免误杀合法饮食问法
        excluded = any(_negative_hit(q, n) for n in negs)
        auto = bool(s.auto_activate and hit and not excluded)
        if on or auto:  # J8：手动开启 = 用户主动要，负向词只影响自动激活
            out.append(s)
    return out


def build_skills_hint(db: Session, skills: list[Skill], budget: int = 8000) -> str:
    """B5/E18：把技能指令（含绑定记忆）拼成 system prompt 片段；总量受 budget 限制。"""
    if not skills:
        return ""
    HEADER = "\n\n已启用的技能（按需使用）：\n"
    entries: list[tuple[str, str]] = []  # (技能名, 行文本)
    for sk in skills:
        line = f"- [{sk.name}] {sk.instructions}"
        if sk.memory_entity:
            facts = memory_context(db, sk.memory_entity)
            if facts:
                line += f"（该技能绑定的记忆 {sk.memory_entity}：{'；'.join(facts)}）"
        entries.append((sk.name, line))
    # K2/L2：预算按「最终拼出的字符串」真实计算；note 自身也受预算约束（超了截断）
    dropped: list[str] = []
    while True:
        note = f"\n（因预算未注入：{', '.join(dropped)}）" if dropped else ""
        body = HEADER + "\n".join(line for _n, line in entries) + note
        if len(body) <= budget or not entries:
            break
        name, _line = entries.pop()
        dropped.insert(0, name)
        log.warning("skill %s skipped: prompt budget %s exceeded", name, budget)
    if not entries and dropped:
        # 全部被丢弃时，note 也不能超预算
        note = f"（因预算未注入：{', '.join(dropped)}）"
        if len(note) > budget:
            note = note[: max(0, budget - 1)] + "…"
    lines = [line for _n, line in entries]
    if not lines:
        return note
    if dropped:
        note = f"\n（因预算未注入：{', '.join(dropped)}）"
    return HEADER + "\n".join(lines) + note


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
    out = []
    for f in rows:
        v = f.value
        if len(v) > 200:  # E18：截断加显式标记，避免模型把截断值当完整值
            v = v[:197] + "…(截断)"
        out.append(f"{f.attribute} = {v}")
    return out


def memory_fact_count(db: Session, entity_id: str) -> int:
    from sqlalchemy import func, select

    from anchorline.models import Fact

    return int(
        db.scalar(select(func.count()).select_from(Fact).where(Fact.entity_id == entity_id, Fact.valid_to.is_(None))) or 0
    )
