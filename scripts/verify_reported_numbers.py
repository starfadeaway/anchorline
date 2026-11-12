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
LEGACY_P = {0.1098, 0.252, 0.25, 0.0011}  # 0.0011 = B 切片封顶实验的配对检验 p（docs/b_arm_slice_cap_experiment.md）
# H6/G8：以下白名单按「文件 + 语境」限定（全局白名单已移除）。
# 收集方式：清空字典 → 跑 verify → 把每个 MISSING 值归到它实际出现的文件（逐条确认后写入）。
KNOWN_PCT_BY_FILE: dict[str, set[float]] = {}
PP_RAW_BY_FILE: dict[str, set[float]] = {}
LEGACY_PP_BY_FILE: dict[str, set[float]] = {}
LEGACY_ACC_BY_FILE: dict[str, set[float]] = {}
# 覆盖率类，按文件限定（audit_report 的声称值；CI 现场算的当前值是 69/63）
FILE_PCT = {"reports/audit_report.md": {45, 69, 71, 63}}
INT_PCT_WHITELIST = {100}  # 常数基线（100%）可全局放行；覆盖率类见 FILE_PCT


# H6/G8：文件级白名单（由实测收集：只在它实际出现的文件里放行）
KNOWN_PCT_BY_FILE.update({
    "reports/aa_pilot_report.md": {6.3},
    "reports/m2_l2_extraction.md": {1.39},
    "reports/m3_2x2.md": {12.0},
    "reports/m3_d_intent.md": {1.9, 44.4, 65.1},
    "reports/m3_summary.md": {12.0, 43.51},
    "reports/stability_runs.md": {11.7, 12.0, 12.3},
    "reports/v1_ku_eval.md": {44.4, 44.44, 65.08, 65.1, 77.78, 98.6},
})
PP_RAW_BY_FILE.update({
    "reports/_flow_d.md": {6.3},
    "reports/aa_pilot_report.md": {6.3},
    "reports/d_arm_154.md": {0.65, 3.9, 6.3},
    "reports/d_arm_154_neighbor.md": {6.3},
    "reports/d_arm_154_run2.md": {6.3},
    "reports/d_arm_pilot.md": {0.5, 6.3},
    "reports/lorekeeper_bridge.md": {4.17, 6.25, 12.5},
    "reports/m3_c1.md": {6.3},
    "reports/m3_d_intent.md": {6.3},
    "reports/m3_summary.md": {0.6, 0.65, 6.3, 7.8},
    "reports/stability_runs.md": {0.65, 1.03, 2.96, 6.3},
    "reports/v1_ku_eval.md": {20.6, 77.8},
})
LEGACY_PP_BY_FILE.update({
    "reports/d_arm_154.md": {3.9},
    "reports/d_arm_pilot.md": {0.5},
    "reports/lorekeeper_bridge.md": {4.17, 6.25, 12.5},
    "reports/m3_summary.md": {7.8},
    "reports/stability_runs.md": {1.03, 2.96},
    "reports/v1_ku_eval.md": {20.6, 77.8},
})

P4_PAT = re.compile(r"(?<![\d.])(\d\.\d{4,6})(?!\d)")
PCT_PAT = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,2})?)%")
SIGNED_PP_PAT = re.compile(r"([+\-\u2212]\d+\.\d+)\s*pp")
SIX_PAT = re.compile(r"(?<![\d.])(0?\.\d{6})(?!\d)")
P_PAT = re.compile(r"p\s*[=：:]\s*\**\s*((?:0?|1)\.\d{1,6}|[01]\.0)")
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
            except Exception as exc:  # T7：坏产物不能静默缩小白名单
                print(f"WARN: 产物无法读取（白名单将变小）：{path}: {exc}")
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
    if not os.environ.get("ANCHORLINE_VERIFY_QUIET"):
        print(f"白名单规模：num4={len(p4 | acc4 | diff4 | LEGACY_P | extra['num4'])} acc2={len(acc2 | extra['acc2'])} p={len(p4 | LEGACY_P)}")
    return {
        "num4": p4 | acc4 | diff4 | LEGACY_P | extra["num4"],
        "acc2": acc2 | extra["acc2"],
        "pp2": pp2,  # H6/G8：pp 白名单改为文件级
        "p_raw": p4 | LEGACY_P,
    }


ROW_PAT = re.compile(
    r"^\|\s*([A-Za-z0-9_]+)\s*(?:->|\u2192)\s*([A-Za-z0-9_]+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|"
)
# E2/G4：按文件映射（不同报告的臂名可能指不同代次；legacy 报告在方向检查里整体豁免）
ARM_FULL = {"B": "B_run3", "C1": "C1", "C2": "C2", "D": "D_run3", "D_neighbor": "D_neighbor"}
ARM_BY_FILE = {
    # m3_summary 默认 run3；run2 对照用显式臂名（B_run2 → C2）
}
LEGACY_REPORTS = {"reports/d_arm_154.md"}  # 第一代产物（有废弃标注），方向检查豁免
# G7：单主题报告的 p 值可以绑定到文件级对比（句子不必写出臂名）
FILE_P_BINDINGS = {
    "reports/m3_d_intent.md": ["D_run3_vs_D_intent", "D_run3_vs_D_run2"],  # H5：两处 p 恰好同为 0.8145
    "reports/m3_c1.md": ["B_run3_vs_C1", "C1_vs_D_run3", "C1_vs_D_neighbor"],
    "reports/m3_168.md": ["B_vs_D_168_run2"],
    "reports/m3_168_run3.md": ["B_vs_D_168_run3"],
}


def check_file_p_binding(text: str, out: dict, rel: str) -> int:
    keys = FILE_P_BINDINGS.get(rel)
    if not keys:
        return 0
    allowed = {round(float(out[k]["p_exact"]), 4) for k in keys if out.get(k)}
    bad = 0
    key_pat = re.compile(r"（([A-Za-z0-9_]+_vs_[A-Za-z0-9_]+)）")
    for m in re.finditer(r"p\s*[=：:]\s*\**\s*(0?\.\d{1,6})", text):
        v = round(float(m.group(1)), min(4, len(m.group(1).split(".")[1])))
        # H5：p 后显式标注了 comparison key 时，按该 key 精确绑定（同值 p 不再混淆）
        ann = key_pat.search(text, m.end(), min(len(text), m.end() + 40))
        if ann and out.get(ann.group(1)):
            expected = round(float(out[ann.group(1)]["p_exact"]), 4)
            if abs(v - expected) > 1e-9:
                print(f"MISMATCH {rel}: p={m.group(1)} 标注为 {ann.group(1)}，应为 {expected}")
                bad += 1
            continue
        if not any(abs(v - a) < 1e-9 for a in allowed):
            print(f"MISMATCH {rel}: 文件级 p={m.group(1)} 不属于 {sorted(allowed)}")
            bad += 1
    return bad


def _find_comparison(out: dict, a: str, b: str, rel: str = ""):
    """E2/G4/K6：显式臂名（B_run2/D_run2）优先，其次文件映射，最后默认（run3）。"""
    run2_map = {"B_run2": "B_run2", "D_run2": "D_run2"}
    candidates = ([run2_map] if (a in run2_map or b in run2_map) else []) + [ARM_BY_FILE.get(rel, {}), ARM_FULL]
    for mapping in candidates:
        fa = mapping.get(a, a)
        fb = mapping.get(b, b)
        for key, row in out.items():
            parts = key.split("_vs_")
            if len(parts) != 2:
                continue
            left, right = parts
            if (left == fa and right == fb) or (left == fb and right == fa):
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
        row = _find_comparison(out, a, b, rel)
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


def check_hybrid_direction(text: str, out: dict, rel: str) -> int:
    """E1/E8：hybrid 报告的带符号配对差方向必须与重算一致（覆盖全文件，跳过同臂复跑行）。"""
    if "hybrid" not in rel:
        return 0
    keys = [k for k in ("D_run3_vs_D_hybrid", "D_run2_vs_D_hybrid", "D_neighbor_vs_D_hybrid") if out.get(k)]
    if not keys:
        return 0
    expected_set = {-float(out[k]["diff_a_minus_b"]) * 100 for k in keys}
    bad = 0
    for line in text.splitlines():
        if ("复跑" in line or "vs D_run2" in line) and "+1.30pp" in line:
            continue  # 只放过同臂复跑的这个具体值，不再整行跳过
        m = re.search(r"([+\-\u2212]\d+\.\d+)\s*pp", line)
        if not m:
            continue
        got = float(m.group(1).replace("\u2212", "-"))
        if not any((got > 0) == (e > 0) and abs(abs(got) - abs(e)) <= 0.06 for e in expected_set):
            print(f"MISMATCH {rel}: hybrid 方向 {m.group(1)}pp 不属于 {sorted(round(e, 2) for e in expected_set)}")
            bad += 1
    return bad


_SEG_GAP = r"[\d\.\s\*%（）()／/,，:：;；—\-]{0,24}?"
SEG_PAT = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\b" + _SEG_GAP + r"(?:vs\b|\u2192|->)" + _SEG_GAP + r"\b([A-Z][A-Za-z0-9_]*)\b")


def check_hybrid_diff_row(text: str, out: dict, rel: str) -> int:
    """F1(a)：hybrid 报告的「配对差（hybrid − 向量）」行（无 pp）也要校验方向。"""
    if "hybrid" not in rel:
        return 0
    row = out.get("D_run3_vs_D_hybrid")
    if row is None:
        return 0
    expected = -float(row["diff_a_minus_b"]) * 100
    bad = 0
    for line in text.splitlines():
        if "配对差" not in line or "hybrid" not in line.lower():
            continue
        m = re.search(r"([+\-\u2212]\d+\.\d+)", line)
        if not m:
            continue
        got = float(m.group(1).replace("\u2212", "-"))
        scale = 0.01 if abs(got) <= 1.0 else 1.0
        if (got > 0) != (expected > 0) or abs(abs(got) / scale - abs(expected)) > 0.06:
            print(f"MISMATCH {rel}: 配对差行 {m.group(1)} 应为 {expected:+.2f}")
            bad += 1
    return bad


def check_paragraph_bindings(text: str, out: dict, rel: str) -> int:
    """E7：散文段落里出现 `A vs B` / `A -> B` 时，段内 p 值必须属于该对比。"""
    bad = 0
    if rel == "reports/d_arm_154.md":
        return 0  # 第一代产物（legacy），见废弃标注
    for para in re.split(r"[。\n]\s*", text):
        segs = [(m.start(), m.group(1), m.group(2)) for m in SEG_PAT.finditer(para)]
        if not segs:
            continue
        for pm in re.finditer(r"p\s*[=：:]\s*\**\s*((?:0?|1)\.\d{1,6}|[01]\.0)", para):
            prev = [
                s
                for s in segs
                if s[0] <= pm.start()
                and pm.start() - s[0] <= 120
                and not any(ch in para[s[0] : pm.start()] for ch in "。；;\n")
            ]
            if not prev:
                continue
            _, a, b = prev[-1]
            row = _find_comparison(out, a, b, rel)
            if row is None:
                continue
            allowed_p = round(float(row["p_exact"]), 4)
            v = round(float(pm.group(1)), min(4, len(pm.group(1).split(".")[1])))
            if abs(v - allowed_p) > 1e-9:
                print(f"MISMATCH {rel}: 段落 {a} vs {b} 引用的 p={pm.group(1)} 应为 {allowed_p}")
                bad += 1
    return bad


def _direction_diff(row: dict, forward: bool) -> float:
    """返回 forward=True 时 (Y − X) 的百分点，False 时 (X − Y)。"""
    du = float(row["diff_a_minus_b"]) * 100  # a − b
    return -du if forward else du


def check_direction_all(text: str, out: dict, rel: str) -> int:
    """F1/K5：每个带符号 pp 绑定最近的前置对比；「约」概述值与同臂复跑差跳过。"""
    if rel in LEGACY_REPORTS:
        return 0
    bad = 0
    for line in text.splitlines():
        segs = [(m.end(), m.group(1), m.group(2)) for m in SEG_PAT.finditer(line)]
        if not segs:
            continue
        for pm in re.finditer(r"([+\-\u2212]?\d+(?:\.\d+)?)\s*pp", line):
            if "约" in line[max(0, pm.start() - 6) : pm.start()]:
                continue
            prev = [s for s in segs if s[0] <= pm.start() and pm.start() - s[0] <= 120]
            if not prev:
                continue
            _, a, b = prev[-1]
            row = _find_comparison(out, a, b, rel)
            if row is None:
                continue
            exps = {_direction_diff(row, forward=True)}
            raw_txt = pm.group(1).replace("\u2212", "-")
            got = float(raw_txt)
            if ("复跑" in line or "vs D_run2" in line) and abs(abs(got) - 1.3) < 0.06:
                continue
            if raw_txt[0] not in "+-":
                ok = any(abs(abs(got) - abs(e)) <= 0.06 for e in exps)
            else:
                ok = any((got > 0) == (e > 0) and abs(abs(got) - abs(e)) <= 0.06 for e in exps)
            if not ok:
                print(f"MISMATCH {rel}: 方向 {a}->{b} 的 {pm.group(1)}pp 不属于 {sorted(round(e, 2) for e in exps)}")
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
            v = round(float(m.group(1)), 4)
            if not any(abs(v - round(a, 4)) < 1e-9 for a in allow["num4"]):
                print(f"MISMATCH {rel}: 4 位数字 {m.group(1)} 不在重算集合")
                file_bad += 1
        file_pct = FILE_PCT.get(rel, set())
        for m in SIX_PAT.finditer(text):
            v = float(m.group(1))
            if not any(abs(v - float(x)) < 5e-5 for x in allow["p_raw"]):
                print(f"MISMATCH {rel}: 6 位 p {m.group(1)} 与重算 p 不匹配")
                file_bad += 1
        for m in PCT_PAT.finditer(text):
            v = float(m.group(1))
            if v == int(v) and int(v) in INT_PCT_WHITELIST:
                continue
            known = (
                {float(x) for x in KNOWN_PCT_BY_FILE.get(rel, set())}
                | {float(x) for x in file_pct}
                | {float(x) for x in LEGACY_ACC_BY_FILE.get(rel, set())}
            )
            if any(abs(v - a) < 0.06 for a in allow["acc2"]) or any(abs(v - a) < 0.06 for a in known):
                continue
            print(f"MISMATCH {rel}: 百分比 {m.group(1)}% 不属于重算值/已知值")
            file_bad += 1
        for m in re.finditer(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*pp", text):
            raw = float(m.group(1))
            digits = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
            # J7：按书写位数四舍五入后精确匹配（3.2 与 3.3 不再等价）
            allowed = {round(abs(float(r["diff_a_minus_b"])) * 100, digits) for r in out.values()}
            known = {round(float(x), digits) for x in PP_RAW_BY_FILE.get(rel, set())}
            if raw in allowed or raw in known:
                continue
            print(f"MISMATCH {rel}: 配对差 {m.group(1)}pp（裸值）不在重算/已知集合")
            file_bad += 1
        for m in SIGNED_PP_PAT.finditer(text):
            v = abs(float(m.group(1).replace("\u2212", "-").replace("+", "")))
            extra_pp = {round(float(x), 2) for x in LEGACY_PP_BY_FILE.get(rel, set())}
            if not any(abs(v - a) < 0.06 for a in (allow["pp2"] | extra_pp)):
                print(f"MISMATCH {rel}: 配对差 {m.group(1)}pp 不在集合")
                file_bad += 1
        file_bad += check_comparison_rows(text, out, rel)
        file_bad += check_hybrid_direction(text, out, rel)
        file_bad += check_hybrid_diff_row(text, out, rel)
        file_bad += check_paragraph_bindings(text, out, rel)
        file_bad += check_direction_all(text, out, rel)
        file_bad += check_file_p_binding(text, out, rel)
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
        "D_run3_vs_D_run2": ("d_arm_154_run3.json", "d_arm_154_run2.json"),
        "B_run3_vs_B_run2": ("b_arm_154_run3.json", "b_arm_154_run2.json"),
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

    # C2 源文件自报（对照 B_run2）：c2_arm_154.json 内含 b_accuracy / paired_diff / p
    try:
        c2 = json.load(open(os.path.join(EVAL, "c2_arm_154.json"), encoding="utf-8"))
        if isinstance(c2.get("paired_diff_c2_minus_b"), (int, float)):
            out["B_run2_vs_C2"] = {
                "a_file": "b_arm_154_run2.json (self-reported in c2_arm_154.json)",
                "b_file": "c2_arm_154.json",
                "n": len(c2.get("per_question") or []) or 154,
                "accuracy_a": round(float(c2["b_accuracy"]), 4),
                "accuracy_b": round(float(c2["c2_accuracy"]), 4),
                "diff_a_minus_b": round(-float(c2["paired_diff_c2_minus_b"]), 4),
                "p_exact": round(float(c2["paired_permutation_pvalue"]), 4),
            }
            print(f"B_run2_vs_C2(self): n={out['B_run2_vs_C2']['n']} p_exact={out['B_run2_vs_C2']['p_exact']:.4f}")
    except Exception as exc:
        print(f"WARN: B_run2_vs_C2 读取失败（该 comparison 不参与校验）：{exc}")

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
