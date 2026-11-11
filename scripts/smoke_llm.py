# -*- coding: utf-8 -*-
"""一次性 smoke test：reader / judge / embedding 三个端点是否可用。

不打印任何 key；只打印状态与长度。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from anchorline.config import Settings  # noqa: E402
from anchorline.llm import embedding_client, judge_client, reader_client  # noqa: E402


def main() -> int:
    s = Settings()
    print("reader model:", s.deepseek_reader_model, "| base:", bool(s.deepseek_base_url), "| key:", bool(s.deepseek_api_key))
    print("judge  model:", s.deepseek_judge_model)
    print("embed  model:", s.siliconflow_embedding_model, "| base:", bool(s.siliconflow_base_url), "| key:", bool(s.siliconflow_api_key))

    out = reader_client(s).complete([{"role": "user", "content": "Reply with exactly: OK"}], max_tokens=256)
    print("reader reply:", out[:40].replace("\n", " "))

    emb = embedding_client(s).embed(["anchorline smoke test"])
    print("embedding dim:", len(emb[0]), "n:", len(emb))

    jout = judge_client(s).complete([
        {"role": "system", "content": "You are a strict grader. Reply only with 1 or 0."},
        {"role": "user", "content": "Reference: 25:50. Prediction: twenty-five minutes fifty seconds. Grade."},
    ], max_tokens=256)
    print("judge reply:", jout[:20].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
