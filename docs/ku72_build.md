# V1-KU 72 题构建报告（可入库版）

> 配套协议：`docs/annotation-protocol-ku78.md`（v2）
> 生成脚本：`dataset/v1/build_ku72.py`（读 `longmemeval_s_cleaned.json` + `order_recheck.json`）
> 产物：`data/annotations/ku72.jsonl`（72 行骨架；不含任何 session 原文）
> 材料（**不入库**，含 session 原文）：`dataset/v1/manual16.md`、`dataset/v1/pilot10.md`

## 1. 分层结果

| 层 | 问句形态 | 题数 | 来源 |
|---|---|---|---|
| 1a | `current` | **49** | answer 唯一命中较晚索引 gold session |
| 1b | `retrospective` | **7** | answer 唯一命中较早索引 gold session |
| — | `manual_needed` | **16** | 14 NEITHER + 2 BOTH |
| 1c | `abstention`（`_abs`） | **6** | 不进 72 |

**72 = 49 + 7 + 16**。16 题判层后，1a/1b 分母需重算 —— **72 与 168 一样仍是 provisional。**

## 2. `data/annotations/ku72.jsonl` 字段状态

| 字段 | 已预填 | 待人工 |
|---|---|---|
| `question_id` / `question` | ✅ | — |
| `query_form` | ✅（49 current / 7 retrospective / 16 manual_needed） | 16 题判层 |
| `new_value` | ✅ 官方 `answer`（只读） | 1b 题需按「answer = 旧值」对调角色 |
| `stale_source_session_id` / `new_source_session_id` | ✅（按索引序） | — |
| `session_order_source` | ✅（`answer_match_index` / `manual`） | 16 题人工 |
| `gold_session_index` | ✅（0 = 较早索引，1 = 较晚索引） | 16 题为 null |
| `stale_value` | ❌ | **全部 72 题需人工确认** |
| `conflict_type` / `expected_resolution` / `entity` / `match_mode` | ❌ | **全部 72 题** |

## 3. Pilot 10 题（先标这 10 题，schema 定死后才批量标）

| # | question_id | 类型 | 用途 |
|---|---|---|---|
| 1 | `5a4f22c0` | current | 回溯限定词指**非时间实体**（`previous company` 类），检验关键词一刀切 |
| 2–5 | `6aeb4375` / `830ce83f` / `852ce960` / `945e3d21` | current | 常规现行值题 |
| 6 | `07741c44` | retrospective | `initially` |
| 7 | `50635ada` | retrospective | `previous … before` |
| 8 | `0ddfec37` | retrospective | `first three months` |
| 9 | `6aeb4375_abs` | abstention | 拒答变体 |
| 10 | `6a1eabeb` | manual_needed | BOTH/NEITHER 流程压力 |

> ⚠️ **未覆盖的风险**：49 道 `current` 题的官方 `answer` 归一化后**均 ≤ 6 token**（实测 0 道长答案）。因此 pilot 无法覆盖「长答案匹配器稳定性」这一项；协议 Step 2.5 原定的「至少 1 道长答案」在自动定位集上无样本。报告需在局限里写明，或在 16 题人工判层后补一条长答案样本。

## 4. 下一步（V1）

1. 人工读 `dataset/v1/pilot10.md`，按 schema 标 10 题 → 定死 schema。
2. 批量标剩余 62 题 + 16 题人工判层（`manual16.md`）。
3. 16 题判层后重算 1a/1b 分母。
4. 16 题自重复（间隔 ≥7 天）+ 跨模型交叉复核。
5. 判定规则固化（exact / normalized / fuzzy）+ fuzzy 阈值 0.7/0.8/0.9 敏感性分析。

## 5. 纪律

- **不看日期判新旧**：按 haystack 数组索引顺序；唯一反例 `618f13b2` 已在协议记录。
- **1b 题的 answer 是旧值**：`new_value` 字段仍存官方 answer，人工必须对调 stale/new 角色。
- 指标名一律「**与标注协议的一致率**」，不用「裁决准确率」。
- `session` 原文**不入库**（`.gitignore` 已排除 `dataset/v1/*.md`）。
