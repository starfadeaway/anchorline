# V1-KU 72 题标注与分母台账（v3.1，已完成标注）

> 协议：`docs/annotation-protocol-ku78.md`（v3 + v3.1）
> 数据：`data/annotations/ku72.jsonl`（72 行，不含 session 原文，可入库）
> 分母：`data/annotations/ku72_denominators.json`
> 标注材料与原始记录：`dataset/v1/`（本地保留、不入库）
> 合并脚本：`scripts/merge_annotations.py`；构建：`scripts/build_ku72.py`；材料：`scripts/make_annotation_batch.py`

## 1. 状态

**72 题全部完成人工标注**（pilot10 10 题 + 剩余 63 题），schema v3.1 定稿。无 `manual_needed`、无 abstention 混入 72。

## 2. 分层与分母（最终）

| 层 | 问句形态 | 题数 | 指标 |
|---|---|---|---|
| **1a** | `current` | **63** | 与标注协议的一致率（分母 63）；过期事实率（有效分母 **60**） |
| **1b** | `retrospective` | **9** | 回溯一致率（取到旧值才算对） |
| **1c** | `abstention`（`_abs`） | **6** | 单列，不进 1a/1b |

- **1a + 1b = 72**。
- **过期事实率有效分母 = 63 − 1（占位旧值 `5a4f22c0`）− 2（无旧值 `22d2cb42`、`5c40ec5b`）= 60**。
- 与标注协议的一致率分母用 63（所有 current 题都能判）。

> 72 与 168 一样：本文件的分母是「标注完成后」的口径；报告定稿时仍写明「V1-KU 75→72 的剔除依据（6 道 `_abs`）」。

## 3. 标注流程（已完成）

1. **pilot10**（10 题）：定死 schema，暴露 Q1–Q5（new_value 语义、gold_session_index、abstention null、占位词、06 数据歧义）→ v3 定稿。
2. **剩余 63 题**：`manual15.md` + `remaining48.md`；15 道 manual 全部判层（14 current + 1 retrospective `10e09553`），48 道批标。
3. **合并**：`scripts/merge_annotations.py` 把 pilot10-v2（9 行）+ remaining-fixed（63 行）写回 `ku72.jsonl`；校验 0 errors。
4. **分母重算**：见上表。

## 4. 特殊题清单（报告时必须单列/说明）

| 类型 | question_id | 处理 |
|---|---|---|
| 占位旧值 | `5a4f22c0` | `stale_value="Old Company"`（assistant 表格占位），`stale_value_is_placeholder=true`；**不进过期事实率** |
| 无旧值（首次发生） | `22d2cb42`、`5c40ec5b` | `stale_value=null`；**不进过期事实率** |
| 复合答案 / 双槽位 | `031748ae`、`f685340e`、`c4ea545c`、`c6853660` | `new_value` 填具体当前值；官方复合句在 `official_answer`；`query_form=current` |
| 措辞差异 | `89941a94` | 题目 `gravel bike` vs 原文 `new hybrid bike`；答案由 road bike 支持，保留，note 标注 |
| 日期反序已知题 | `618f13b2` | 按 haystack 索引判（不改） |

## 5. 下一步（V1）

1. **自重复一致性**：随机 16 题（含上述特殊题）间隔 ≥7 天重标，比对一致率。
2. **跨模型交叉标注**：用与主 judge 不同的模型独立标同样 16 题。
3. **判定规则固化**：exact / normalized / fuzzy；fuzzy 阈值 0.7 / 0.8 / 0.9 敏感性分析，报告结论是否翻转。
4. **复核记录表**：填 `docs/annotation-protocol-ku78.md` §7（标注者、两轮日期、一致率、交叉模型）。
5. 词汇级坑：`89941a94` 的 old/new 都是 "Yes (...)"，过期检测区分度弱，聚合时单列。

## 6. 复现

```powershell
.venv\Scripts\python.exe scripts\build_ku72.py            # 生成骨架
.venv\Scripts\python.exe scripts\make_annotation_batch.py # 生成待标材料
# （人工标注）
.venv\Scripts\python.exe scripts\fix_and_validate_remaining.py
.venv\Scripts\python.exe scripts\merge_annotations.py     # 合并 + 分母
```
