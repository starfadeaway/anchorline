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
LEGACY_ACC = {13.6, 9.7, 21.0, 15.0, 44.4, 44.44, 98.6, 65.1, 65.08, 77.78}
LEGACY_PP = {0.5, 2.96, 1.03, 3.9, 4.17, 6.25, 7.8, 12.5, 20.6, 77.8}
# 其他实验的整数百分比（非本表准确率）：LoreKeeper/V1 等
INT_PCT_WHITELIST = {45, 69, 71, 100}

P4_PAT = re.compile(r"(?<![\d.])(\d\.\d{4})(?!\d)")
PCT_PAT = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,2})?)%")
SIGNED_PP_PAT = re.compile(r"([+\-\u2212]\d+\.\d+)\s*pp")
P_PAT = re.compile(r"p\s*[=：:]\s*\**\s*(0?\.\d{1,6})")
MD_GLOB = "reports/*.md"


def _json_numbers() -> dict[str, set]:
    """扫描 data/eval、data/v1 等 JSON 的数值；百分比只从 accuracy 类字段推导（避免 0.99 之类的偶然值放行）。"""
    import glob

    num4: set[float] = set()
    acc2: set[float] = set()

    def walk(obj, key: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, str(k))
        elif isinstance(obj, list):
            for x in obj:
                walk(x, key)
        elif isinstance(obj, bool):
            return
        elif isinstance(obj, (int, float)):
            v = float(obj)
            num4.add(round(v, 4))
            k = key.lower()
            if "acc" in k or "accuracy" in k:
                acc2.add(round(v * 100, 2) if 0.0 <= v <= 1.0 else round(v, 2))

    for pattern in ("data/eval/*.json", "data/v1/*.json", "data/*.json"):
        for path in glob.glob(os.path.join(ROOT, pattern)):
            try:
                data = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            walk(data)
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


ROW_PAT = re.compile(
    r"^\|\s*([A-Za-z0-9_]+)\s*(?:->|\u2192)\s*([A-Za-z0-9_]+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|"
)
ARM_ALIASES = {"B": "B_run3", "C1": "C1", "C2": "C2", "D": "D_run3", "D_neighbor": "D_neighbor"}


def _find_comparison(out: dict, a: str, b: str):
    """按行内的 A -> B 找到对应 comparison（a 侧可能是 B_run3 等全名）。"""
    for key, row in out.items():
        parts = key.split("_vs_")
        if len(parts) != 2:
            continue
        left, right = parts
        for cand_a in (a, ARM_ALIASES.get(a, a)):
            for cand_b in (b, ARM_ALIASES.get(b, b)):
                if (left.startswith(cand_a) or cand_a in left) and (right.startswith(cand_b) or cand_b in right):
                    return row
    return None


def check_comparison_rows(text: str, out: dict, rel: str) -> int:
    """D2：m3_2x2 表格行按「对比」绑定允许值，避免把别的对比的合法数字当成这个对比的。"""
    bad = 0
    for line in text.splitlines():
        m = ROW_PAT.match(line)
        if not m:
            continue
        a, b, acc_col, _n, pp_col, p_col = m.groups()
        row = _find_comparison(out, a, b)
        if row is None:
            continue
        acc_a, acc_b = float(row["accuracy_a"]), float(row["accuracy_b"])
        p = round(float(row["p_exact"]), 4)
        # 准确率列（A → B 顺序）
        for v in re.findall(r"(?<![\d.])(\d\.\d{4})", acc_col):
            if not any(abs(float(v) - x) < 1e-9 for x in (round(acc_a, 4), round(acc_b, 4))):
                print(f"MISMATCH {rel}: 行 {a}->{b} 的准确率 {v} 不属于该对比")
                bad += 1
        # 配对差（B − A 方向，m3_2x2 表格里是比例而非 pp）
        expected_diff = round(acc_b - acc_a, 4)
        pp = re.search(r"([+\-\u2212]?\d+\.\d+)", pp_col)
        if pp:
            got = float(pp.group(1).replace("\u2212", "-"))
            if abs(got - expected_diff) > 0.001:
                print(f"MISMATCH {rel}: 行 {a}->{b} 的配对差 {got} 应为 {expected_diff:+.4f}")
                bad += 1
        # p 值
        for v in re.findall(r"(?<![\d.])(0?\.\d{4})", p_col):
            if abs(float(v) - p) > 1e-9:
                print(f"MISMATCH {rel}: 行 {a}->{b} 的 p={v} 应为 {p}")
                bad += 1
    return bad


def check_signed_pp(text: str, out: dict, rel: str) -> int:
    """D4：带符号配对差的符号必须与重算方向一致（符号 = 结论方向）。"""
    bad = 0
    for line in text.splitlines():
        m = re.search(r"([\u2212\-\+]\d+\.\d+)\s*pp", line)
        if not m:
            continue
        got = float(m.group(1).replace("\u2212", "-"))
        mag = abs(got)
        # 该行提到的对比：找 |diff|*100 匹配的 comparison
        matches = [
            (key, row)
            for key, row in out.items()
            if abs(round(abs(float(row["diff_a_minus_b"])) * 100, 2) - round(mag, 2)) < 0.06
        ]
        if not matches:
            continue  # 其他实验的差值（如 lorekeeper/v1_ku）由白名单兜底
        # 用行内文字判断方向：出现 "A − B" / "A−B" 时取 a−b 的符号
        sign_ok = False
        for key, row in matches:
            parts = key.split("_vs_")
            if len(parts) != 2:
                continue
            left, right = parts
            diff = float(row["diff_a_minus_b"])
            if f"{left}" in line and f"{right}" in line:
                if got * diff > 0:
                    sign_ok = True
            elif left in line or right in line:
                # 只提到一侧时，只能校验数值（符号可能因表述方向相反）
                sign_ok = True
        if not sign_ok:
            print(f"MISMATCH {rel}: 配对差 {m.group(1)}pp 的符号与重算方向不一致")
            bad += 1
    return bad


def check_hybrid_direction(text: str, out: dict, rel: str) -> int:
    """D4：hybrid 报告的方向行（hybrid − 向量）符号必须与重算一致。"""
    if "hybrid" not in rel:
        return 0
    keys = [k for k in ("D_run3_vs_D_hybrid", "D_run2_vs_D_hybrid", "D_neighbor_vs_D_hybrid") if out.get(k)]
    if not keys:
        return 0
    expected_set = {-float(out[k]["diff_a_minus_b"]) * 100 for k in keys}  # hybrid − 向量
    bad = 0
    for line in text.splitlines():
        if "pp" in line and re.search(r"[+\-\u2212]\d+\.\d+\s*pp", line) and ("hybrid" in line.lower() or "\u5411\u91cf" in line):
            m = re.search(r"([+\-\u2212]\d+\.\d+)\s*pp", line)
            if not m:
                continue
            got = float(m.group(1).replace("\u2212", "-"))
            if not any((got > 0) == (e > 0) and abs(abs(got) - abs(e)) <= 0.06 for e in expected_set):
                print(f"MISMATCH {rel}: hybrid 方向 {m.group(1)}pp 不属于 {sorted(round(e, 2) for e in expected_set)}")
                bad += 1
    return bad


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
            legacy2 = {round(x, digits) for x in LEGACY_P}
            if digits < 3 and v not in (0.0, 1.0) and v not in legacy2:
                print(f"MISMATCH {rel}: p={m.group(1)} 精度不足（p 值至少写 3 位小数；0/1 除外）")
                file_bad += 1
                continue
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
            if v == int(v) and int(v) in INT_PCT_WHITELIST:
                continue
            if not any(abs(v - a) < 0.06 for a in allow["acc2"]):
                print(f"MISMATCH {rel}: 百分比 {m.group(1)}% 不在准确率集合")
                file_bad += 1
        for m in SIGNED_PP_PAT.finditer(text):
            v = abs(float(m.group(1).replace("\u2212", "-").replace("+", "")))
            if not any(abs(v - a) < 0.06 for a in allow["pp2"]):
                print(f"MISMATCH {rel}: 配对差 {m.group(1)}pp 不在集合")
                file_bad += 1
        file_bad += check_comparison_rows(text, out, rel)
        file_bad += check_hybrid_direction(text, out, rel)
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
