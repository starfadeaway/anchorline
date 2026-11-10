# -*- coding: utf-8 -*-
"""生成交给 MiniMax Code 的标注包（盲标，不含人类标注）。

输出目录：dataset/v1/minimax-package/
  README.md            给 MiniMax Code 的任务说明（先读这个）
  annotation-spec.md   精简协议（字段、规则、输出格式）
  examples.md          2 个虚构 few-shot 示例（不来自数据集，避免泄露）
  template.jsonl       72 行空白模板（只预填 question_id / official_answer / is_abstention）
  questions/<qid>.md   72 个逐题材料（题面 + 官方 answer + 两个 gold session 全文，标注 A=较早 / B=较晚）

纪律：
  - 不预填 official_answer_role / gold_session_index / source ids（避免泄露方向）
  - 不给 ku72.jsonl（人类标注）——盲标
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KU = os.path.join(ROOT, "dataset", "longmemeval_s_cleaned.json")
ANN = os.path.join(ROOT, "data", "annotations", "ku72.jsonl")
OUT = os.path.join(ROOT, "dataset", "v1", "minimax-package")


def msg_lines(session) -> str:
    parts = []
    for m in session or []:
        role = m.get("role", "?")
        content = str(m.get("content", "")).replace("\r", "").strip()
        parts.append(f"### {role}\n{content}")
    return "\n\n".join(parts)


README = """# Anchorline V1-KU 标注任务（MiniMax Code）

你是一名严格的标注员。任务：对 72 道 LongMemEval-S `knowledge-update` 题，按给定协议标注「旧值 / 当前值 / 问句形态」。

## 你要读的文件

1. `annotation-spec.md` —— 字段定义、判定规则、输出格式（**必读**）
2. `examples.md` —— 2 个虚构示例（只学格式与判断方式）
3. `template.jsonl` —— 72 行空白模板；每行已填 `question_id`、`official_answer`、`is_abstention`
4. `questions/<qid>.md` —— 每题材料：题面、官方 answer、两个 gold session 全文

## 每题的流程

1. 读 `questions/<qid>.md`；
2. 只看两个 gold session（材料里已只给这两个），按 **session A = 较早、session B = 较晚** 判新旧（**不要用日期**）；
3. 判断 `query_form`：
   - `current`：问当前状态；
   - `retrospective`：问旧值/初始值（`initially` / `previous` / `before` / `first N months`）；
   - `abstention`：题目无法回答或前提错误；
   - 双槽位题（同时问「刚上任时/现在」「previously/now」）→ **`current`**，旧值写 `stale_value`。
4. 填 `new_value`（当前值，具体值）与 `stale_value`（旧值，具体值；**无旧值写 null**）；
5. 填 `conflict_type`（`时效`/`语义`/`偏好反转`）、`expected_resolution`（`覆盖`/`并存`/`标失效`/`升级人工`）、`entity`、`match_mode`（`exact`/`normalized`/`fuzzy`）、`note`；
6. 把这一行 JSON 追加到 `annotations-minimax.jsonl`（**不要改 template.jsonl**）。

## 硬规则

- **不要看 `data/annotations/ku72.jsonl`**（那是人类标注，会污染盲标）。
- **不要用日期判新旧**；只看 session A/B 的顺序（haystack 索引）。
- **retrospective 题的官方 answer 是旧值**；当前值在较晚 session。
- **复合答案**（官方 answer 是 Yes/No 或 Previously…Currently…）：`new_value` 填具体当前值、`stale_value` 填具体旧值，不要把整句抄进来。
- `stale_value` 只在「旧状态已发生」时填；「还没送修 / 还没见面 / 只是候选店」→ `stale_value=null`，note 说明。
- 不确定就标 `query_form="manual_needed"` 并在 `note` 写原因，**不要硬猜**。
- `stale_source_session_id` / `new_source_session_id` 填材料里的 session id；`gold_session_index` 填当前值所在 session 的相对序（0=较早 A，1=较晚 B）。

## 输出

文件：`annotations-minimax.jsonl`，72 行，每行一个 JSON，字段与 `template.jsonl` 一致。
`official_answer_role` 与 `official_answer_session_index` **留空即可**，由我们的脚本根据 `query_form` 回填。

## 完成标准

- 72 行，`question_id` 与模板一一对应；
- 没有 `null` 的 `query_form`（不确定用 `manual_needed`）；
- 每行 `note` 简短说明依据。
"""

SPEC = """# 标注协议（精简版，MiniMax 用）

## 字段

| 字段 | 取值 | 说明 |
|---|---|---|
| `question_id` | 字符串 | 模板已给，不要改 |
| `query_form` | `current` / `retrospective` / `abstention` / `manual_needed` | 问句形态；双槽位 → current |
| `new_value` | 字符串 | **语义当前值**（具体值，不是 Yes/No 结论、不是整句） |
| `stale_value` | 字符串或 null | **旧值**；无旧值（首次发生/未发生/占位）→ null |
| `stale_source_session_id` | session id | 旧值所在 session |
| `new_source_session_id` | session id | 当前值所在 session |
| `session_order_source` | `manual` | 本任务一律 `manual` |
| `gold_session_index` | 0 / 1 | 当前值所在 session 的相对序（0=较早 A，1=较晚 B） |
| `is_abstention` | true / false | 模板已给 |
| `conflict_type` | `时效` / `语义` / `偏好反转` / null | 知识更新通常是 `时效` |
| `expected_resolution` | `覆盖` / `并存` / `标失效` / `升级人工` / null | 通常 `覆盖` |
| `entity` | 字符串 | 被更新的属性（英文） |
| `match_mode` | `exact` / `normalized` / `fuzzy` / null | 值能否精确匹配；数字/货币/星期建议 `normalized` |
| `note` | 字符串 | 一句话依据 |

## 判定顺序（每题照做）

1. 读题面：问的是「现在」还是「过去某个值」？
2. 读 session A（较早）与 B（较晚）：找出同一个属性的旧值与当前值。
3. 判 `query_form`：问当前 → `current`；问旧值 → `retrospective`；双槽位 → `current`；无法判 → `manual_needed`。
4. 填值：`new_value`=当前值；`stale_value`=旧值（无则 null）。
5. 标 `entity`、`conflict_type`（通常时效）、`expected_resolution`（通常覆盖）、`match_mode`、`note`。

## 常见陷阱

- **不要用日期**判新旧；只看 A/B 顺序。
- **retrospective 的官方 answer 是旧值**，不要把它当 `new_value`。
- 复合答案（`Yes` / `Previously...Currently...`）→ 拆成具体旧值与当前值。
- 首次发生（旧状态是「还没做」）→ `stale_value=null`。
- 占位词（如表格里的 `Old Company`）→ `stale_value` 保留原词并标 `stale_value_is_placeholder=true`。
- 同一题里两个值都是 `Yes`（布尔未变、只是数量变）→ `stale_value`/`new_value` 填具体数量描述，不要都填 Yes。
"""

EXAMPLES = """# Few-shot 示例（虚构，仅示范格式与判断）

## 示例 1：current + 数字更新

- 题面：`How many books have I read this year?`
- 官方 answer：`12`
- session A（较早，idx 3）：user：「I've read 9 books this year.」
- session B（较晚，idx 20）：user：「I've read 12 books this year now.」

输出：

```json
{"question_id":"EXAMPLE_CURRENT","query_form":"current","new_value":"12","stale_value":"9","stale_source_session_id":"example_1","new_source_session_id":"example_2","session_order_source":"manual","gold_session_index":1,"is_abstention":false,"conflict_type":"时效","expected_resolution":"覆盖","entity":"books read this year","match_mode":"exact","note":"A=9, B=12; current question"}
```

## 示例 2：retrospective + 旧值

- 题面：`What was my previous gym schedule?`
- 官方 answer：`three times a week`
- session A（较早，idx 5）：user：「I go to the gym three times a week.」
- session B（较晚，idx 18）：user：「I go to the gym four times a week now.」

输出：

```json
{"question_id":"EXAMPLE_RETRO","query_form":"retrospective","new_value":"four times a week","stale_value":"three times a week","stale_source_session_id":"example_1","new_source_session_id":"example_2","session_order_source":"manual","gold_session_index":1,"is_abstention":false,"conflict_type":"时效","expected_resolution":"覆盖","entity":"gym frequency","match_mode":"normalized","note":"asks previous schedule; official answer is old value"}
```
"""


def main() -> int:
    ku = json.load(open(KU, encoding="utf-8"))
    qs = {q["question_id"]: q for q in ku if q.get("question_type") == "knowledge-update"}
    rows = [json.loads(line) for line in open(ANN, encoding="utf-8") if line.strip()]

    os.makedirs(os.path.join(OUT, "questions"), exist_ok=True)
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(README)
    with open(os.path.join(OUT, "annotation-spec.md"), "w", encoding="utf-8") as f:
        f.write(SPEC)
    with open(os.path.join(OUT, "examples.md"), "w", encoding="utf-8") as f:
        f.write(EXAMPLES)

    tpl = []
    for r in rows:
        qid = r["question_id"]
        q = qs[qid]
        sess = q["haystack_sessions"]
        sid = q["haystack_session_ids"]
        gold = sorted(q.get("answer_session_ids") or [], key=lambda s: sid.index(s))
        blocks = []
        for label, s in zip(("A (earlier)", "B (later)"), gold):
            i = sid.index(s)
            blocks.append(f"## Session {label}: `{s}` (haystack index {i})\n\n{msg_lines(sess[i])}")
        with open(os.path.join(OUT, "questions", f"{qid}.md"), "w", encoding="utf-8") as f:
            f.write(f"# {qid}\n\n")
            f.write(f"**Question**: {q['question']}\n\n")
            f.write(f"**Official answer**: {q.get('answer')}\n\n")
            f.write("> 判新旧只看 A/B 顺序；不要用日期。retrospective 题的官方 answer 是旧值。\n\n")
            f.write("\n\n".join(blocks) + "\n")
        tpl.append({
            "question_id": qid,
            "query_form": "",
            "new_value": "",
            "official_answer": q.get("answer"),
            "official_answer_role": "",          # 留空，避免泄露方向
            "official_answer_session_index": "",
            "stale_value": "",
            "stale_value_is_placeholder": "",
            "stale_source_session_id": "",
            "new_source_session_id": "",
            "session_order_source": "manual",
            "gold_session_index": "",
            "is_abstention": False,
            "conflict_type": "",
            "expected_resolution": "",
            "entity": "",
            "match_mode": "",
            "note": "",
        })

    with open(os.path.join(OUT, "template.jsonl"), "w", encoding="utf-8") as f:
        for t in tpl:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    total = 0
    for root, _, files in os.walk(OUT):
        for fn in files:
            total += os.path.getsize(os.path.join(root, fn))
    print(f"package: {OUT}")
    print(f"questions={len(tpl)} files={sum(len(fs) for _,_,fs in os.walk(OUT))} sizeMB={total/1024/1024:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
