# -*- coding: utf-8 -*-
"""生成界面截图到 docs/screenshots/（本地用，截图不入库）。

前置：
  1. 后端 API 在 127.0.0.1:8000；
  2. 前端 dev 在 127.0.0.1:5173（`cd frontend && npm run dev`）；
  3. 已安装 Playwright（frontend/node_modules/@playwright/test）。

用法：
  .venv\\Scripts\\python.exe scripts\\make_screenshots.py
  .venv\\Scripts\\python.exe scripts\\make_screenshots.py --base http://127.0.0.1:5173 --out docs/screenshots
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [
    ("01-chat", "/chat"),
    ("02-memory", "/memory"),
    ("03-eval", "/eval"),
    ("04-review", "/review"),
    ("05-reports", "/reports"),
    ("06-monitor", "/monitor"),
    ("07-settings", "/settings"),
]


def _alive(url: str, timeout: float = 3.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "screenshots"))
    args = ap.parse_args()

    if not _alive(args.api + "/health"):
        print(f"API 不可用：{args.api}/health（先启动 uvicorn）", file=sys.stderr)
        return 1
    if not _alive(args.base + "/"):
        print(f"前端不可用：{args.base}（先 cd frontend && npm run dev）", file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)

    npx = "npx.cmd" if os.name == "nt" else "npx"
    for name, path in PAGES:
        dst = os.path.join(args.out, f"{name}.png")
        cmd = [
            npx, "playwright", "screenshot",
            "--viewport-size=1400,811",
            "--wait-for-timeout=2500",
            args.base + path,
            dst,
        ]
        r = subprocess.run(cmd, cwd=os.path.join(ROOT, "frontend"), capture_output=True, text=True)
        print(f"{name}: {'ok' if r.returncode == 0 else 'FAIL'} -> {dst}")
        if r.returncode != 0:
            print(r.stderr[-400:], file=sys.stderr)
    print("注意：截图直接来自运行中的实例（不脱敏）；只有实例里全是测试数据时才可提交。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
