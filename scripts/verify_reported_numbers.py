# -*- coding: utf-8 -*-
"""报告数字一致性校验：从 data/eval/*.json 重算配对对比，与 reports/reported_numbers.json 比对。

不一致 → exit 1（CI 挂进 eval-regression job）。
用法：.venv\\Scripts\\python.exe scripts/verify_reported_numbers.py [--write]
  --write  重新生成 reports/reported_numbers.json（仅当确认报告数字已同步时用）
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from eval_stats import paired_compare  # noqa: E402

EVAL = os.path.join(ROOT, "data", "eval")
BASELINE = os.path.join(ROOT, "reports", "reported_numbers.json")


def load_means(fname: str) -> dict[str, float]:
    path = os.path.join(EVAL, fname)
    if not os.path.exists(path):
        raise FileNotFoundError(fname)
    data = json.load(open(path, encoding="utf-8"))
    return {str(r["question_id"]): float(r.get("mean", 0.0)) for r in data.get("per_question", [])}


def _168_means(fname: str, key: str) -> dict[str, float]:
    data = json.load(open(os.path.join(EVAL, fname), encoding="utf-8"))
    out = {}
    for r in data.get("gotchas_rows", []):
        v = r.get(key)
        if v is not None:
            out[str(r["question_id"])] = float(v)
    # 154 确定性题：用对应臂的 run3 结果合并（168 = 154 + 14）
    return out


# 历史/附录数字（第一代产物、被取代的旧结论）——显式白名单，改动白名单需说明原因
LEGACY_P = {0.1098, 0.252, 0.25}
LEGACY_ACC = {13.6, 9.7, 21.0, 15.0, 44.4, 44.44, 98.6}
LEGACY_PP = {0.5, 2.96, 1.03, 3.9, 4.17, 6.25, 7.8, 12.5, 20.6, 77.8}

P4_PAT = re.compile(r"(?<![\d.])(\d\.\d{4})(?!\d)")
PCT_PAT = re.compile(r"(?<![\d.])(\d{1,3}\.\d{1,2})%")
SIGNED_PP_PAT = re.compile(r"([+\-\u2212]\d+\.\d+)\s*pp")
P_PAT = re.compile(r"p\s*[=：:]\s*\**\s*(0?\.\d{1,6})")
MD_GLOB = "reports/*.md"


def _json_numbers() -> dict[str, set]:
    """扫描 data/eval、data/v1 等 JSON 里的真实数值（md 会引用这些产物）。"""
    import glob

    num4: set[float] = set()
    acc2: set[float] = set()
    for pattern in ("data/eval/*.json", "data/v1/*.json", "data/*.json"):
        for path in glob.glob(os.path.join(ROOT, pattern)):
            try:
                data = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            stack = [data]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    stack.extend(cur.values())
                elif isinstance(cur, list):
                    stack.extend(cur)
                elif isinstance(cur, bool):
                    continue
                elif isinstance(cur, (int, float)):
                    v = float(cur)
                    num4.add(round(v, 4))
                    if 0.0 <= v <= 1.0:
                        acc2.add(round(v * 100, 2))
                    elif 1.0 < v <= 100.0:
                        acc2.add(round(v, 2))
    return {"num4": num4, "acc2": acc2}


def _global_allowed(out: dict) -> dict[str, set]:
    """所有重算条目的 p / accuracy / diff 并集（md 会跨文件引用，所以用全局集合）。"""
    p4, acc4, acc2, pp2, diff4 = set(), set(), set(), set(), set()
    for row in out.values():
        p4.add(round(float(row["p_exact"]), 4))
        for side in ("accuracy_a", "accuracy_b"):
            acc = float(row[side])
            acc4.add(round(acc, 4))
            acc2.add(round(acc * 100, 2))
        diff = abs(float(row["diff_a_minus_b"]))
        diff4.add(round(diff, 4))
        pp2.add(round(diff * 100, 2))
        pp2.add(round(diff * 100, 1))
    extra = _json_numbers()
    return {
        "num4": p4 | acc4 | diff4 | LEGACY_P | extra["num4"],
        "acc2": acc2 | LEGACY_ACC | extra["acc2"],
        "pp2": pp2 | LEGACY_PP,
        "p_raw": p4 | LEGACY_P,
    }


def check_markdown(out: dict) -> int:
    """A2：从 md 解析数字，与重算集合比对（子串存在性 → 数值比对）。"""
    bad = 0
    allow = _global_allowed(out)
    import glob

    paths = sorted(glob.glob(os.path.join(ROOT, "reports", "*.md")))
    checked = 0
    for path in paths:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        text = open(path, encoding="utf-8").read()
        file_bad = 0
        for m in P_PAT.finditer(text):
            digits = len(m.group(1).split(".")[1])
            v = round(float(m.group(1)), digits)
            cands = {round(x, digits) for x in allow["p_raw"]}
            if v not in cands:
                print(f"MISMATCH {rel}: p={m.group(1)} 与重算 p 不匹配（按 {digits} 位取整）")
                file_bad += 1
        for m in P4_PAT.finditer(text):
            v = float(m.group(1))
            if not any(abs(v - a) < 1e-9 for a in allow["num4"]):
                print(f"MISMATCH {rel}: 4 位数字 {m.group(1)} 不在重算集合")
                file_bad += 1
        for m in PCT_PAT.finditer(text):
            v = float(m.group(1))
            if not (40.0 <= v <= 100.0):
                continue  # 翻转率 12%、覆盖率等非准确率百分比
            if not any(abs(v - a) < 0.06 for a in allow["acc2"]):
                print(f"MISMATCH {rel}: 百分比 {m.group(1)}% 不在准确率集合")
                file_bad += 1
        for m in SIGNED_PP_PAT.finditer(text):
            v = abs(float(m.group(1).replace("\u2212", "-").replace("+", "")))
            if not any(abs(v - a) < 0.06 for a in allow["pp2"]):
                print(f"MISMATCH {rel}: 配对差 {m.group(1)}pp 不在集合")
                file_bad += 1
        bad += file_bad
        checked += 1
    print(f"md 解析校验：覆盖 {checked} 个文件，问题 {bad} 处")
    return bad


def main() -> int:
    write = "--write" in sys.argv
    comparisons = {
        "B_run2_vs_D_run2": ("b_arm_154_run2.json", "d_arm_154_run2.json"),
        "B_run3_vs_D_run3": ("b_arm_154_run3.json", "d_arm_154_run3.json"),
        "B_run3_vs_C1": ("b_arm_154_run3.json", "c1_arm_154.json"),
        "B_run3_vs_C2": ("b_arm_154_run3.json", "c2_arm_154.json"),
        "C1_vs_D_run3": ("c1_arm_154.json", "d_arm_154_run3.json"),
        "C2_vs_D_run3": ("c2_arm_154.json", "d_arm_154_run3.json"),
        "C1_vs_D_neighbor": ("c1_arm_154.json", "d_arm_154_neighbor.json"),
        "D_run3_vs_D_neighbor": ("d_arm_154_run3.json", "d_arm_154_neighbor.json"),
        "D_run3_vs_D_hybrid": ("d_arm_154_run3.json", "d_arm_154_hybrid.json"),
        "D_run3_vs_D_intent": ("d_arm_154_run3.json", "d_arm_154_intent.json"),
        "D_run2_vs_D_hybrid": ("d_arm_154_run2.json", "d_arm_154_hybrid.json"),
        "D_neighbor_vs_D_hybrid": ("d_arm_154_neighbor.json", "d_arm_154_hybrid.json"),
    }
    out = {}
    for name, (a_file, b_file) in comparisons.items():
        a = load_means(a_file)
        b = load_means(b_file)
        r = paired_compare(a, b)
        out[name] = {
            "a_file": a_file,
            "b_file": b_file,
            "n": r["n"],
            "accuracy_a": round(r["accuracy_a"], 4),
            "accuracy_b": round(r["accuracy_b"], 4),
            "diff_a_minus_b": round(r["diff_a_minus_b"], 4),
            "p_exact": round(r["p_exact"], 4),
        }
        print(f"{name}: n={r['n']} A={r['accuracy_a']:.4f} B={r['accuracy_b']:.4f} "
              f"diff={r['diff_a_minus_b']:+.4f} p_exact={r['p_exact']:.4f}")

    # 168 口径：154 确定性 + 14 judge
    for run, b154_file, d154_file, judge_file in [
        ("run2", "b_arm_154_run2.json", "d_arm_154_run2.json", "arm_168_run2.json"),
        ("run3", "b_arm_154_run3.json", "d_arm_154_run3.json", "arm_168_run3.json"),
    ]:
        b154 = load_means(b154_file)
        d154 = load_means(d154_file)
        b168 = {**b154, **_168_means(judge_file, "b_label")}
        d168 = {**d154, **_168_means(judge_file, "d_label")}
        r168 = paired_compare(b168, d168)
        out[f"B_vs_D_168_{run}"] = {
            "a_file": f"{b154_file} + {judge_file}(b_label)",
            "b_file": f"{d154_file} + {judge_file}(d_label)",
            "n": r168["n"],
            "accuracy_a": round(r168["accuracy_a"], 4),
            "accuracy_b": round(r168["accuracy_b"], 4),
            "diff_a_minus_b": round(r168["diff_a_minus_b"], 4),
            "p_exact": round(r168["p_exact"], 4),
        }
        print(f"B_vs_D_168_{run}: n={r168['n']} A={r168['accuracy_a']:.4f} B={r168['accuracy_b']:.4f} "
              f"diff={r168['diff_a_minus_b']:+.4f} p_exact={r168['p_exact']:.4f}")

    if write:
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"written: {BASELINE}")
        return 0

    if not os.path.exists(BASELINE):
        print(f"缺少基线 {BASELINE}：先跑 --write 并把报告数字同步到重算值。")
        return 1
    baseline = json.load(open(BASELINE, encoding="utf-8"))
    bad = 0
    for name, cur in out.items():
        ref = baseline.get(name)
        if ref is None:
            print(f"MISSING baseline: {name}")
            bad += 1
            continue
        for key in ("n", "accuracy_a", "accuracy_b", "diff_a_minus_b", "p_exact"):
            if abs(float(ref[key]) - float(cur[key])) > 1e-4:
                print(f"MISMATCH {name}.{key}: baseline={ref[key]} recomputed={cur[key]}")
                bad += 1
    bad += check_markdown(out)
    if bad:
        print(f"\n{bad} mismatch(es)：报告数字与重算不一致。")
        return 1
    print("\nOK：报告数字与重算一致（无 numpy 依赖）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
