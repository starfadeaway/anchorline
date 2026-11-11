# -*- coding: utf-8 -*-
"""报告数字一致性校验：从 data/eval/*.json 重算配对对比，与 reports/reported_numbers.json 比对。

不一致 → exit 1（CI 挂进 eval-regression job）。
用法：.venv\\Scripts\\python.exe scripts/verify_reported_numbers.py [--write]
  --write  重新生成 reports/reported_numbers.json（仅当确认报告数字已同步时用）
"""
from __future__ import annotations

import json
import os
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


MD_ASSERTIONS = {
    "reports/d_arm_154_hybrid.md": ["55.84%", "−10.4pp", "0.019520", "0.048767", "0.098371"],
    "reports/m3_2x2.md": ["0.0385", "0.4869", "0.0336"],
    "reports/m3_168.md": ["0.0186"],
    "reports/m3_168_run3.md": ["0.0541"],
    "reports/m3_d_intent.md": ["0.8145"],
    "reports/stability_runs.md": ["0.0115", "0.0385"],
    "reports/m3_summary.md": ["0.0115"],
}


def check_markdown() -> int:
    """Z3：报告 .md 里的关键数字也要接受校验（此前只校验 JSON 重算值）。"""
    bad = 0
    for rel, needles in MD_ASSERTIONS.items():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print(f"MISSING md: {rel}")
            bad += 1
            continue
        text = open(path, encoding="utf-8").read()
        for needle in needles:
            if needle not in text:
                print(f"MISMATCH md {rel}: 缺少 {needle}")
                bad += 1
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
    bad += check_markdown()
    if bad:
        print(f"\n{bad} mismatch(es)：报告数字与重算不一致。")
        return 1
    print("\nOK：报告数字与重算一致（无 numpy 依赖）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
