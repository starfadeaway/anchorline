# -*- coding: utf-8 -*-
"""L1 观测摘要：state / session → 事件（谁、何时、做了什么、在哪个页面）。

口径（v0.8 §5）：
  - V2：一条轨迹 = states × accessibility_tree（含 action / thought / url）；
  - L1 不复述 a11y 树，只产出「可回答、可追溯」的事件行；
  - 事件行保留 url + action + thought 摘要，供后续 L2 事实抽取与 trace 使用。

本模块只做确定性转换，不调用 LLM；LLM 摘要属于 L2 的抽取步骤。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    index: int
    url: str
    action: str
    thought: str

    def to_line(self) -> str:
        parts = [f"#{self.index}"]
        if self.url:
            parts.append(f"@{self.url}")
        if self.action:
            parts.append(f"action={self.action}")
        if self.thought:
            parts.append(f"thought={self.thought}")
        return " | ".join(parts)


def _clip(text: object, limit: int) -> str:
    s = "" if text is None else str(text)
    s = " ".join(s.split())
    return s[:limit] if limit and len(s) > limit else s


def summarize_states(states: list[dict], *, thought_limit: int = 240, action_limit: int = 240) -> list[Event]:
    """把一条轨迹的 states 转成事件序列（跳过非 dict 与完全空白的 state）。"""
    events: list[Event] = []
    for i, st in enumerate(states):
        if not isinstance(st, dict):
            continue
        action = _clip(st.get("action"), action_limit)
        thought = _clip(st.get("thought"), thought_limit)
        url = _clip(st.get("url"), 300)
        if not (action or thought or url):
            continue
        events.append(Event(index=i, url=url, action=action, thought=thought))
    return events


def events_to_text(events: list[Event]) -> str:
    return "\n".join(e.to_line() for e in events)
