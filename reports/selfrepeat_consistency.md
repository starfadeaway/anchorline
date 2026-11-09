# V1 自重复标注一致性（复核报告）

> 对象：同一标注者（MiniMax agent）在 **25.7 小时**后对 16 题盲标第二遍（第一遍 2026-11-08 22:45，第二遍 2026-11-10 00:26）。
> 复核方式：本仓库独立重算（不采信合层自述），比对文件为第一遍 `dataset/v1/minimax-package/annotations-minimax.jsonl`。
> 盲标合规：第二遍只读包内 README/监工清单/template/questions（worker 报告自述，未触碰第一批结果）。

## 1. 完整性

- 16 行，`question_id` 顺序与 `template.jsonl` 逐行一致；
- 18 字段/行，UTF-8、LF；
- 4 个原始分片 `.shards/sr_w{1..4}.jsonl` 保留（一手证据）。

## 2. 一致率

| 字段 | 逐字 | 语义归一 | 说明 |
|---|---|---|---|
| `query_form` | **16/16** | — | 完全一致 |
| `gold_session_index` | **16/16** | — | 完全一致（合并层把 2 行 worker 原填 0 规范为 1，见下） |
| `expected_resolution` | **16/16** | — | 完全一致 |
| `new_value` | 13/16 | **16/16** | 3 处同义不同表述（原文核对过） |
| `stale_value` | 11/16 | 15/16 | 4 处同义；**1 处真分歧**（`b01defab`） |
| `conflict_type` | 3/16 | 词表版本差异 | 第一遍 v1 词表（时效/语义/偏好反转），第二遍 v3.2（时效/数值/否定/无），非判断漂移 |
| `entity` | 3/16 | 自由文本 | 措辞差异 |
| `match_mode` | 9/16 | 判据粒度 | 差异 |

**三项关键字段（query_form / gold_session_index / new_value 语义）：实质一致 16/16。**

## 3. 待仲裁（未改）

1. **`b01defab` 的 `stale_value`**：第一遍 `null`（协议陷阱条款：首次发生、旧状态“还没做” → null）；第二遍 `'No'`。按协议应保留第一遍，待人工拍板。
2. **README v3.2 表述冲突**：README 写「retrospective 题为旧值，取官方答案语义」，与 spec 正文 + `examples.md` 的 `EXAMPLE_RETRO`（`new_value=当前值B / stale_value=旧值A / gold_session_index=1`）及拍板不一致。需修正 README。
3. 合并层把 `07741c44`、`89941a94` 两行 worker 原填（gsi=0）按“答案值所在 session”规范为 1——与第一遍一致，记录在此。

## 4. 局限（必须随结论一起报告）

1. **间隔仅 25.7 小时**（包 README 标称 48h、v0.8 协议要求 ≥7 天）→ 一致率偏高，**不能当协议级稳定性证据**；
2. 无第二人类标注者，只能表述为「单人工标注 + 自重复 + 跨模型交叉」；
3. 第二遍依据的 `annotation-spec.md` v3.2 在盘上不存在（只有 v1 精简版），实际依据是 selfrepeat README + v1 spec + 拍板；
4. MiniMax 报告称 `ku72.jsonl` 不存在——**误报**：文件在 `data/annotations/ku72.jsonl`（不在 `dataset/v1/`），复核时已作为第一遍比对源使用；
5. 自重复包与第二遍结果在 `dataset/`（不入库），仅本报告可推送。
