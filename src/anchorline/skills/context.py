# -*- coding: utf-8 -*-
"""当前请求的活动技能（contextvar）：供 memory_write 标记事实来源技能。"""
from contextvars import ContextVar

ACTIVE_SKILLS: ContextVar[list[str] | None] = ContextVar("anchorline_active_skills", default=None)  # T15：默认 None，取值时 or []
