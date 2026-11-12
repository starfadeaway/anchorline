# -*- coding: utf-8 -*-
"""仓库/数据目录的统一路径契约（§55：容器里包在 site-packages，禁止各模块自己算根目录）。

优先级：环境变量 > 源码树位置。
- ANCHORLINE_ROOT：仓库根（Dockerfile 设为 /app）
- ANCHORLINE_LANCEDB：索引目录（Dockerfile 设为 /app/data/lancedb）
- ANCHORLINE_DATASET_V2：V2 数据集目录（容器里挂载 dataset 时用）
"""
from __future__ import annotations

import os

# src/anchorline/paths.py -> anchorline -> src -> 仓库根
ROOT = os.environ.get("ANCHORLINE_ROOT") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DATA_DIR = os.path.join(ROOT, "data")
LANCEDB_DIR = os.environ.get("ANCHORLINE_LANCEDB") or os.path.join(DATA_DIR, "lancedb")
DATASET_V2_DIR = os.environ.get("ANCHORLINE_DATASET_V2") or os.path.join(ROOT, "dataset", "v2")
EVAL_DIR = os.path.join(DATA_DIR, "eval")
