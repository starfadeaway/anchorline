# -*- coding: utf-8 -*-
"""当前请求的活动技能（contextvar）：供 memory_write 标记事实来源技能。"""
from contextvars import ContextVar

ACTIVE_SKILLS: ContextVar[list[str]] = ContextVar("anchorline_active_skills", default=[])
