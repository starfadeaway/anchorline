# -*- coding: utf-8 -*-
"""Build the V1-KU 72-question annotation skeleton + manual-review material.

Inputs (read-only):
  dataset/longmemeval_s_cleaned.json   (MIT layer; session 原文只读)
  dataset/order_recheck.json           (authoritative 新旧方向 + 分层产物)

Outputs:
  data/annotations/ku72.jsonl          72 rows, schema fields only (no session text) -> can be committed
  dataset/v1/pilot10.md                pilot 10 题材料（含 session 原文，不入库）
  dataset/v1/build_report.md           统计（含少量题面，不入库）
  （manual 判层材料由 scripts/make_annotation_batch.py 生成，本脚本不再产出重复文件）

Rules (docs/annotation-protocol-ku78.md):
  - 新旧方向按 haystack 索引顺序，不看日期
  - 1a_current: answer 在较晚索引 session
  - 1b_retrospective: answer 是旧值，在较早索引 session
  - 6 道 _abs 不进 72
  - 16 道 manual_needed（14 NEITHER + 2 BOTH）人工判层
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "dataset")
OUT_ANN = os.path.join(BASE, "data", "annotations")
OUT_V1 = os.path.join(DATA, "v1")

# pilot10 人工判层结果（协议 v3 §10）
MANUAL_OVERRIDES = {
    "6a1eabeb": {
        "query_form": "current",
        "note": "manual(pilot10): 官方 answer 25:50 是当前值，旧值 27:12；层次判为 current（1a）",
    },
}


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def gold_pair(q, order_row):
    ids = q["haystack_session_ids"]
    gold = list(q.get("answer_session_ids") or [])
    pos = sorted(gold, key=lambda s: ids.index(s))
    early, late = pos[0], pos[-1]
    return early, late, ids.index(early), ids.index(late)


def msg_lines(session):
    out = []
    for m in session or []:
        role = m.get("role", "?")
        content = str(m.get("content", "")).replace("\r", "")
        out.append(f"**{role}**: {content}")
    return "\n\n".join(out)


def main():
    import argparse
    import shutil

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="目标已存在时仍覆盖（会先备份到 _backup/）")
    args = ap.parse_args()
    target = os.path.join(OUT_ANN, "ku72.jsonl")
    if os.path.exists(target) and not args.force:
        raise SystemExit(
            f"拒绝覆盖已入库的人工标注：{target}\n"
            "该文件是 M2 评测的 gold（72 行人工标注），build_ku72 只是骨架生成器。\n"
            "如确需重建骨架，请先手动备份，或加 --force（会自动备份）。"
        )
    if os.path.exists(target) and args.force:
        bak_dir = os.path.join(OUT_ANN, "_backup")
        os.makedirs(bak_dir, exist_ok=True)
        shutil.copy2(target, os.path.join(bak_dir, f"ku72.jsonl.bak-{int(__import__('time').time())}"))
    _ = (ap, args)
    q_all = load(os.path.join(DATA, "longmemeval_s_cleaned.json"))
    ku = [x for x in q_all if x.get("question_type") == "knowledge-update"]
    ku_by_id = {x["question_id"]: x for x in ku}
    reco = load(os.path.join(DATA, "order_recheck.json"))
    rows = {r["question_id"]: r for r in reco["rows"]}
    assert len(rows) == 78, len(rows)

    os.makedirs(OUT_ANN, exist_ok=True)
    os.makedirs(OUT_V1, exist_ok=True)

    ann = []
    manual = []
    stats = {"current": 0, "retrospective": 0, "manual": 0, "abstention": 0}

    for qid, r in rows.items():
        q = ku_by_id[qid]
        if r["is_abstention"]:
            stats["abstention"] += 1
            continue
        early, late, ei, li = gold_pair(q, r)
        loc = r["loc"]
        lam = r["layer_prelim"]

        if lam == "1a_current":
            qf, gsi, src = "current", 1, "answer_match_index"
            stale_s, new_s = early, late
            note = "auto: answer 唯一命中较晚索引 session（=当前值）"
            stats["current"] += 1
        elif lam == "1b_retrospective":
            qf, gsi, src = "retrospective", 1, "answer_match_index"  # 当前值在较晚索引
            stale_s, new_s = early, late
            note = "auto: 官方 answer 在较早索引（旧值）；当前值在较晚 session（待人工回填 new_value）"
            stats["retrospective"] += 1
        else:
            qf, gsi, src = "manual_needed", None, "manual"
            stale_s, new_s = early, late
            note = f"auto: loc={loc}；需人工判层 + 定位"
            stats["manual"] += 1

        # pilot 人工判层覆盖（pilot10 已判：6a1eabeb 从 manual_needed → current）
        ov = MANUAL_OVERRIDES.get(qid)
        if ov:
            qf = ov["query_form"]
            gsi = 1 if qf in {"current", "retrospective"} else None
            src = "manual"
            note = ov["note"]
            stats["manual"] -= 1
            stats["current" if qf == "current" else "retrospective"] += 1

        ann.append({
            "question_id": qid,
            "query_form": qf,
            "new_value": "" if qf == "retrospective" else (q.get("answer") or ""),
            "official_answer": q.get("answer"),
            "official_answer_role": "old" if qf == "retrospective" else ("current" if qf == "current" else None),
            "official_answer_session_index": 0 if qf == "retrospective" else (1 if qf == "current" else None),
            "stale_value": "",
            "stale_value_is_placeholder": False,
            "stale_source_session_id": stale_s,
            "new_source_session_id": new_s,
            "session_order_source": src,
            "gold_session_index": gsi,
            "is_abstention": False,
            "conflict_type": "",
            "expected_resolution": "",
            "entity": "",
            "match_mode": "",
            "note": note,
        })

        if qf == "manual_needed":
            manual.append((qid, q, r, early, late, ei, li))

    # --- 72 jsonl ---
    with open(os.path.join(OUT_ANN, "ku72.jsonl"), "w", encoding="utf-8") as f:
        for a in ann:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    # manual 材料由 scripts/make_annotation_batch.py 统一生成（剔除已标题，避免多份重复文件）

    # --- pilot10.md ---
    def pick(pred, k, used):
        out = []
        for a in ann:
            if a["question_id"] in used:
                continue
            if pred(a):
                out.append(a)
                used.add(a["question_id"])
            if len(out) >= k:
                break
        return out

    used = set()
    pilot = []

    def take(a):
        pilot.append(a)
        used.add(a["question_id"])

    # 0) 非时间实体回溯词样本（5a4f22c0 / ba61f0b9）—— 检验关键词一刀切
    for qid in ("5a4f22c0", "ba61f0b9"):
        a = next((x for x in ann if x["question_id"] == qid), None)
        if a and qid not in used:
            take(a)
            break
    # 1) current：至少 1 道长答案（>6 token）
    longs = [a for a in ann if a["query_form"] == "current" and a["question_id"] not in used
             and len(str(a["new_value"]).split()) > 6]
    if longs:
        take(longs[0])
    # 2) current 补到 4 道（5a4f22c0/ba61f0b9 单独算「非时间实体」样本，不占这 4 道）
    n_cur = sum(1 for a in pilot if a["query_form"] == "current" and a["question_id"] not in ("5a4f22c0", "ba61f0b9"))
    pilot += pick(lambda a: a["query_form"] == "current" and a["question_id"] not in ("5a4f22c0", "ba61f0b9"),
                 max(0, 4 - n_cur), used)
    # 3) retrospective 恰 3 道：先覆盖 initially / previous / first N months
    for kw in ("initially", "previous", "first three months"):
        if sum(1 for a in pilot if a["query_form"] == "retrospective") >= 3:
            break
        for a in ann:
            if a["query_form"] != "retrospective" or a["question_id"] in used:
                continue
            qtext = str(ku_by_id[a["question_id"]].get("question") or "").lower()
            if kw in qtext:
                take(a)
                break
    n_ret = sum(1 for a in pilot if a["query_form"] == "retrospective")
    pilot += pick(lambda a: a["query_form"] == "retrospective", max(0, 3 - n_ret), used)
    # abstention
    for qid, r in rows.items():
        if r["is_abstention"]:
            q = ku_by_id[qid]
            pilot.append({"question_id": qid, "question": q["question"], "query_form": "abstention",
                          "new_value": q.get("answer"), "note": "pilot: abstention 样本"})
            used.add(qid)
            break
    # BOTH / NEITHER
    for qid, q, r, early, late, ei, li in manual:
        if qid not in used:
            pilot.append({"question_id": qid, "question": q["question"], "query_form": "manual_needed",
                          "new_value": q.get("answer"), "note": "pilot: 流程压力样本"})
            used.add(qid)
            break

    with open(os.path.join(OUT_V1, "pilot10.md"), "w", encoding="utf-8") as f:
        f.write(f"# V1-KU pilot（{len(pilot)} 题）\n\n")
        f.write("> 材料含 gold session 原文，**不入库**。先标这 %d 题，schema 定死后才批量标。\n\n" % len(pilot))
        for n, a in enumerate(pilot, 1):
            qid = a["question_id"]
            if qid in ku_by_id and qid in rows and not rows[qid]["is_abstention"]:
                q = ku_by_id[qid]
                early, late, ei, li = gold_pair(q, rows[qid])
                dates = q["haystack_dates"]
                f.write(f"\n## {n:02d}. `{qid}` — {a['query_form']}\n\n")
                f.write(f"- **question**: {q['question']}\n- **answer**: {q.get('answer')}\n")
                f.write(f"- **gold**: `{early}` (idx {ei}, {dates[ei]}) | `{late}` (idx {li}, {dates[li]})\n\n")
                for sid, idx in ((early, ei), (late, li)):
                    f.write(f"### session `{sid}` (idx {idx})\n\n")
                    f.write(msg_lines(q["haystack_sessions"][idx]) + "\n\n")
            else:
                q = ku_by_id[qid]
                f.write(f"\n## {n:02d}. `{qid}` — {a['query_form']}\n\n")
                f.write(f"- **question**: {q['question']}\n- **answer**: {q.get('answer')}\n\n")

    # --- build_report.md ---
    with open(os.path.join(OUT_V1, "build_report.md"), "w", encoding="utf-8") as f:
        f.write("# V1-KU 72 题骨架构建报告\n\n")
        f.write("- 78 题 knowledge-update → 72 非拒答 + 6 `_abs`\n")
        f.write(f"- 自动定位：1a current {stats['current']} 题；1b retrospective {stats['retrospective']} 题\n")
        f.write(f"- 待人工：{stats['manual']} 题（NEITHER {stats.get('neither', '?')} + BOTH {stats.get('both', '?')}）\n")
        f.write(f"- 拒答：{stats['abstention']} 题（层 1c，单列）\n")
        f.write(f"- 输出：`data/annotations/ku72.jsonl`（{len(ann)} 行）、`dataset/v1/pilot10.md`；manual 材料用 `scripts/make_annotation_batch.py` 生成\n")
        f.write("\n## 关键提醒\n\n")
        f.write("- 1b 回溯题的官方 answer 是**旧值**；骨架的 `new_value` 字段仍存官方 answer，人工标注时须把 stale/new 角色对调。\n")
        f.write("- `gold_session_index` 采用「两个 gold session 的相对序」（0=较早索引，1=较晚索引）。\n")
        f.write("- 16 题的 `query_form` 留 `manual_needed`，判层后 1a/1b 分母重算。\n")

    print("ANN", len(ann), "manual", len(manual), "pilot", len(pilot))
    print("out:", OUT_ANN, OUT_V1)


if __name__ == "__main__":
    main()
