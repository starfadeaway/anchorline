# -*- coding: utf-8 -*-
"""数据层：锚定数据目录（`dataset/`，本地不入库）。

统一脚本里重复的「加载 questions / small / offsets / index + 取 web 轨迹」逻辑。
只读；不写任何数据文件。
"""
from __future__ import annotations

import json
import os
from typing import Iterator

from anchorline.paths import DATASET_V2_DIR

V2_DIR = DATASET_V2_DIR


def v2_path(name: str) -> str:
    """返回 dataset/v2 下某个文件/目录的绝对路径。"""
    return os.path.join(V2_DIR, name)


def _load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_questions(path: str | None = None) -> dict[str, dict]:
    """questions.jsonl -> {question_id: question}。"""
    qs: dict[str, dict] = {}
    with open(path or v2_path("questions.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                qs[q["id"]] = q
    return qs


def load_small(path: str | None = None) -> dict[str, list[str]]:
    """lme_v2_small.json -> {question_id: [trajectory_id, ...]}（每题 100 条 haystack）。"""
    return _load_json(path or v2_path("lme_v2_small.json"))


def load_traj_index(path: str | None = None) -> dict[str, dict]:
    """traj_index.json：1,870 条轨迹的 domain/environment/goal/outcome/state 摘要。"""
    return _load_json(path or v2_path("traj_index.json"))


def load_traj_offsets(path: str | None = None) -> dict[str, int]:
    """traj_offsets.json：trajectory_id -> 字节偏移（随机 seek，不用重扫 1.2GB）。"""
    return _load_json(path or v2_path("traj_offsets.json"))


def web_question_ids(qs: dict[str, dict] | None = None) -> list[str]:
    """web 域（webarena-*）的题号。"""
    qs = qs or load_questions()
    return [qid for qid, q in qs.items() if str(q.get("environment", "")).startswith("webarena")]


def web_trajectory_ids(
    qs: dict[str, dict] | None = None,
    small: dict[str, list[str]] | None = None,
    idx: dict[str, dict] | None = None,
) -> list[str]:
    """web 240 题引用的唯一轨迹集合（去重、排序；Small 层共 100 条）。"""
    qs = qs or load_questions()
    small = small if small is not None else load_small()
    idx = idx if idx is not None else load_traj_index()
    ids: set[str] = set()
    for qid in web_question_ids(qs):
        for tid in small.get(qid, []):
            if (idx.get(tid) or {}).get("domain") == "web":
                ids.add(tid)
    return sorted(ids)


def get_trajectory(tid: str, offsets: dict[str, int], path: str | None = None) -> dict | None:
    """按偏移 seek 读取一条轨迹的完整 JSON（不重扫整个文件）。"""
    if tid not in offsets:
        return None
    with open(path or v2_path("trajectories.jsonl"), "rb") as fh:
        fh.seek(offsets[tid])
        return json.loads(fh.readline().decode("utf-8"))


def iter_trajectories(
    tids: list[str],
    offsets: dict[str, int] | None = None,
    path: str | None = None,
) -> Iterator[tuple[str, dict]]:
    """按顺序逐条 yield (trajectory_id, trajectory)；只打开文件一次。"""
    offsets = offsets if offsets is not None else load_traj_offsets()
    with open(path or v2_path("trajectories.jsonl"), "rb") as fh:
        for tid in tids:
            if tid not in offsets:
                continue
            fh.seek(offsets[tid])
            yield tid, json.loads(fh.readline().decode("utf-8"))
