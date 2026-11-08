# -*- coding: utf-8 -*-
"""L0 行级去重（v0.8 §5 口径）。

规则（已由 dataset/v2/measure_compression.py 实测，可直接照做）：
  - 同一条轨迹 / 会话内，**行只保留首次出现**；
  - 空行丢弃；
  - 行做 strip 后比较，但保留 strip 后的行文本；
  - **不用**「最后一个 RootWebArea 之前 = 导航壳」—— 该规则在 web 域完全失效。

本模块是记忆层 L0 的生产实现；`dataset/v2/measure_compression.py` 是同口径的测量脚本，
两者必须给出一致的压缩比（M1 退出标准：误差 ≤ 20%）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


def lines_of(text: str) -> list[str]:
    """按测量脚本同口径切行：strip 后丢弃空行。"""
    return [x.strip() for x in text.split("\n") if x.strip()]


@dataclass
class L0Stats:
    raw_lines: int = 0
    novel_lines: int = 0
    raw_chars: int = 0
    novel_chars: int = 0

    @property
    def dup_ratio(self) -> float:
        return 1 - self.novel_lines / self.raw_lines if self.raw_lines else 0.0

    @property
    def compression(self) -> float:
        return self.raw_chars / self.novel_chars if self.novel_chars else 0.0


@dataclass
class L0Deduper:
    """跨 state 的行级去重器（一条轨迹/会话一个实例）。"""

    _seen: set[str] = field(default_factory=set)
    stats: L0Stats = field(default_factory=L0Stats)

    def feed(self, text: str) -> list[str]:
        """输入一个 state 的原文，返回其中**首次出现**的行。"""
        lines = lines_of(text)
        self.stats.raw_lines += len(lines)
        self.stats.raw_chars += len(text)
        novel = [x for x in lines if x not in self._seen]
        self._seen.update(novel)
        self.stats.novel_lines += len(novel)
        # 与测量脚本一致：novel_chars 计 "行长度 + 1(换行)"
        self.stats.novel_chars += sum(len(x) + 1 for x in novel)
        return novel

    def feed_states(self, states: list[str]) -> str:
        """按 state 顺序去重并按 state 边界拼接（state 之间用空行分隔）。"""
        blocks = []
        for s in states:
            novel = self.feed(s or "")
            if novel:
                blocks.append("\n".join(novel))
        return "\n\n".join(blocks)
