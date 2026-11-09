# V1 自重复标注一致性（复核报告 · 仲裁后）

> 对象：同一标注者（MiniMax agent）在 **25.7 小时**后对 16 题盲标第二遍。
> 本仓库独立复核 + 人工仲裁（2026-11-10）：`b01defab` 的 `stale_value` **统一用 `null`**，README 中「retrospective 题为旧值，取官方答案语义」已改为 spec 口径。
> 比对源：第一遍 `dataset/v1/minimax-package/annotations-minimax.jsonl`；人类 gold `data/annotations/ku72.jsonl`。
> 盲标合规：第二遍只读包内 README/监工清单/template/questions（worker 报告自述）。

## 1. 完整性

- 16 行，`question_id` 顺序与 `template.jsonl` 逐行一致；18 字段/行；UTF-8 无 BOM、LF；
- 两个产物：`selfrepeat-minimax.jsonl`（原始第二遍）与 `selfrepeat-minimax.v32.jsonl`（v3.2 合规副本，仅 `5831f84d` 的 `stale_value` 按 v3.2 #11 由 `12` 改 `10`）；
- 4 个原始分片 `.shards/sr_w{1..4}.jsonl` 保留。

## 2. 一致率（n=16）

| 字段 | 第二遍 vs 第一遍 | 第二遍 vs 人类 gold | 说明 |
|---|---|---|---|
| `query_form` | **16/16** | **16/16** | 完全一致 |
| `gold_session_index` | **16/16** | **16/16** | 完全一致 |
| `expected_resolution` | **16/16** | **16/16** | 完全一致 |
| `new_value` | 13/16 字面，**语义 16/16** | 11/16 字面，语义 15/16 | 同义不同表述（人工核对原文） |
| `stale_value` | 12/16 字面，语义 15/16 | 10/16 字面，语义 12/16 | 4 处同义；`b01defab` 仲裁为 null |
| `conflict_type` | 3/16 字面（语义 16/16） | 3/16 字面（语义 16/16） | **词表版本差异**（v1 `时效/语义/偏好反转` vs 包 README `时效/数值/否定/无`），非判断漂移 |

**三项关键字段（query_form / gold_session_index / new_value 语义）：实质一致 16/16。**

六组对比（含 v3.2 修正）详见 `selfrepeat-package/selfrepeat-compare.json`；关键读数：
- 第二遍 vs 人类 gold 的 `new_value` 语义 **16/16**，高于第一遍的 15/16（v3.2 修正后）；
- `conflict_type` 3/16 坐实是协议词表版本差异（第一遍按协议词表全填「时效」，与 gold 72/72 一致）。

## 3. 待决（明天）

1. **role 词表冲突**：拍板用 `current/stale/abstention`，协议与 gold 用 `current/old/null`（`stale`≡`old`）。需定：改协议还是改产物（或只做映射）。
2. **协议文件头版本号** `v2` 未修（正文实为 v3.2）。
3. `5831f84d` 的 `stale_value`：原始产物保留 `12`、v3.2 副本为 `10`；是否把 `10` 作为正式值（人类 gold 也是 `10`）。

## 4. 局限

1. 间隔仅 **25.7 小时**（包 README 标 48h、v0.8 协议要求 ≥7 天）→ 一致率偏高，**不能当协议级稳定性证据**；
2. 无第二人类标注者 → 固定措辞：「单人工标注 + 自重复一致性检查 + 跨模型交叉检查」；
3. `annotation-spec.md` v3.2 已补到包内（9.9 KB）；`ku72.jsonl` 误报已更正（它在 `data/annotations/`）；
4. 自重复包与第二遍结果在 `dataset/`（不入库），本报告可推送。
