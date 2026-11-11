# -*- coding: utf-8 -*-
"""内置技能（Skill）：可开关的提示模块。

技能 = 名称 / 标题 / 描述 / 指令；开关存 DB（skill_toggles），聊天时把启用技能的指令拼进 system prompt。
不引入函数调用或外部工具：技能只影响"怎么回答"，不绕过记忆边界。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    title: str
    description: str
    instructions: str
    memory_entity: str | None = None
    auto_activate: bool = False
    trigger_keywords: str = ""


BUILTIN_SKILLS: list[Skill] = [
    Skill(
        name="run_coach",
        trigger_keywords="跑步,配速,5k,半马,全马,跑量",
        title="跑步教练",
        description="按记忆里的 PB / 目标 / 伤病史给训练建议",
        instructions=(
            "用户问跑步、配速、训练计划时：先检索记忆中的 PB、目标、伤病史；"
            "给出可执行的周计划（跑量/配速区间/休息日）；不要编造未记录的成绩。"
        ),
    ),
    Skill(
        name="diet_plan",
        trigger_keywords="吃,饮食,配餐,忌口,咖啡",
        title="饮食规划",
        description="按饮食偏好 / 禁忌给配餐建议",
        instructions=(
            "用户问吃什么、配餐时：先检索记忆里的饮食偏好与禁忌（如不吃辣、少油少盐）；"
            "优先蒸煮/凉拌；避开明确禁忌；不确定时先问。"
        ),
    ),
    Skill(
        name="kb_search",
        trigger_keywords="原神,星铁,绝区零,wiki,遗器",
        title="知识库问答",
        description="用 kb_search 检索 LoreKeeper 三库 wiki（原神 / 星铁 / 绝区零）",
        instructions=(
            "用户问原神/星铁/绝区零 wiki 内容（角色、遗器、任务）时，用 kb_search 检索；"
            "回答时引用页面标题；不要用事实记忆替代 wiki 复述。"
        ),
    ),
    Skill(
        name="memory_hygiene",
        trigger_keywords="冲突,冗余,记忆整理,失效",
        title="记忆整理",
        description="冲突 / 冗余事实的记忆卫生建议",
        instructions=(
            "发现同一实体+属性有旧值被新值替代时，用 supersedes_id 指向旧事实并保持只有一条当前值；"
            "发现明显冗余/测试数据时提示清理；不确定实体归属时先问。"
        ),
    ),
]

SKILL_BY_NAME: dict[str, Skill] = {s.name: s for s in BUILTIN_SKILLS}
