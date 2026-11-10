# -*- coding: utf-8 -*-
"""轻量请求指标：内存环形缓冲（最近 1000 请求）→ 延迟分位数 / 错误率 / QPS。

不引 Prometheus；单副本本地服务足够。
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

_SAMPLES: deque[tuple[float, str, int, float]] = deque(maxlen=1000)
_LOCK = Lock()


def record(path: str, status: int, duration_ms: float) -> None:
    with _LOCK:
        _SAMPLES.append((time.time(), path, status, duration_ms))


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def snapshot() -> dict:
    with _LOCK:
        rows = list(_SAMPLES)
    if not rows:
        return {"n": 0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "error_rate": 0.0, "qps": 0.0}
    durations = sorted(r[3] for r in rows)
    errors = sum(1 for r in rows if r[2] >= 500)
    window = max(1.0, rows[-1][0] - rows[0][0])
    return {
        "n": len(rows),
        "p50_ms": round(_quantile(durations, 0.50), 1),
        "p95_ms": round(_quantile(durations, 0.95), 1),
        "p99_ms": round(_quantile(durations, 0.99), 1),
        "error_rate": round(errors / len(rows), 4),
        "qps": round(len(rows) / window, 2),
        "recent": [
            {"ts": r[0], "path": r[1], "status": r[2], "ms": round(r[3], 1)}
            for r in rows[-20:]
        ],
    }
