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
    negative_keywords: str = ""  # G9：命中这些词时不激活（防通用词误伤）


BUILTIN_SKILLS: list[Skill] = [
    Skill(
        name="run_coach",
        trigger_keywords="跑步,跑了,配速,5k,半马,全马,跑量",
        negative_keywords="跑步机|跑步鞋",
        title="跑步教练",
        description="按记忆里的 PB / 目标 / 伤病史给训练建议",
        instructions=('用户问跑步、配速、训练计划、伤病恢复时使用。先检索记忆里的 PB、目标、伤病史与最近训练量；再给可执行的周计划（次数/距离/配速区间/休息日），并说明当前处于哪个阶段。给建议时区分「已记录的事实」与「通用训练常识」；不要编造用户没记录过的成绩或伤病。信息不足时先问 1-2 个关键问题（目标距离、每周可训练天数、是否有伤）。'),
    ),
    Skill(
        name="diet_plan",
        trigger_keywords="吃,吃什么,吃啥,饮食,配餐,忌口,咖啡,吃饭",
        negative_keywords="吃苦(?![瓜菜粒叶])|吃了苦|吃亏|吃了亏|吃药|吃了药",
        title="饮食规划",
        description="按饮食偏好 / 禁忌给配餐建议",
        instructions=('用户问吃什么、配餐、忌口时使用。先检索记忆里的饮食偏好、禁忌、过敏与目标（减脂/增肌）；再给具体搭配（早/午/晚 + 加餐），避开明确禁忌。不要推荐用户明确不吃/过敏的食物；不确定时先问。明确标注「通用建议」而非医疗建议。'),
    ),
    Skill(
        name="kb_search",
        trigger_keywords="原神,星铁,绝区零,wiki,遗器",
        negative_keywords="",
        title="知识库问答",
        description="用 kb_search 检索 LoreKeeper 三库 wiki（原神 / 星铁 / 绝区零）",
        instructions=('用户问原神/星铁/绝区零的 wiki 内容（角色、遗器、任务、材料）时使用。先调用 kb_search 检索对应游戏库，再基于页面内容回答并引用页面标题；wiki 事实以检索结果为准，不要用记忆事实替代或补编数值。检索不到时说明「wiki 未检索到」，不要编造。'),
    ),
    Skill(
        name="memory_hygiene",
        trigger_keywords="冲突,冗余,记忆整理,失效,过期",
        negative_keywords="功能失效|链接失效|功能过期|证书过期",
        title="记忆整理",
        description="冲突 / 冗余事实的记忆卫生建议",
        instructions=('用户提到记忆冲突、旧值、冗余、测试数据或「怎么整理记忆」时使用。先检索相关实体的当前值与历史，指出哪条是当前值、哪条已失效、是否还有多条并存；建议用 supersede 标记失效而不是删除；不确定实体归属时先问。不要擅自删除用户记忆。'),
    ),
]

SKILL_BY_NAME: dict[str, Skill] = {s.name: s for s in BUILTIN_SKILLS}
