# M2 记忆质量评测（V1 72 题 gold）

> 用 V1 的 72 题 gold 检验“系统自动判定”与人工标注的一致率；不新标、不改 gold。

> **基线说明（本版新增）**：每个指标必须与「常数基线」（gold 众数占比）对照。
> gold 的 `conflict_type` 72/72 全是「时效」、`expected_resolution` 72/72 全是「覆盖」——**零方差**，
> 常数预测器的准确率是 100%。因此这两个指标在当前 gold 上**低于常数基线，不构成能力指标**。

| 指标 | 一致率 | 常数基线（众数占比） | 结论 |
|---|---|---|---|
| query_form（回溯意图） | 0.9861 | 0.8750（current 63/72） | 高于基线 +11.1pp，有真实信号 ✅ |
| conflict_type（冲突类型） | 0.8889 | **1.0000（时效 72/72）** | 低于基线，**不可评测**（零方差） |
| expected_resolution（裁决） | 0.8472 | **1.0000（覆盖 72/72）** | 低于基线，**不可评测**（零方差） |

> 主集只提供「时效」这一类冲突样本；「语义 / 偏好反转」两类在 `docs/annotation-schema-zh30.md`
> 的自建集里才有（偏好反转 7 条）。跨集结论不能直接迁移，本报告不做类型分列。

## 逐题差异（不一致项）

| qid | 字段 | gold | pred |
|---|---|---|---|
| `d7c942c3` | conflict_type | 时效 | 否定 |
| `07741c44` | conflict_type | 时效 | 无 |
| `07741c44` | expected_resolution | 覆盖 | 并存 |
| `031748ae` | expected_resolution | 覆盖 | 并存 |
| `c4ea545c` | expected_resolution | 覆盖 | 并存 |
| `b01defab` | conflict_type | 时效 | 否定 |
| `22d2cb42` | query_form | current | retrospective |
| `22d2cb42` | conflict_type | 时效 | 无 |
| `22d2cb42` | expected_resolution | 覆盖 | 并存 |
| `50635ada` | expected_resolution | 覆盖 | 并存 |
| `e66b632c` | conflict_type | 时效 | 无 |
| `e66b632c` | expected_resolution | 覆盖 | 并存 |
| `0ddfec37` | conflict_type | 时效 | 无 |
| `dfde3500` | expected_resolution | 覆盖 | 并存 |
| `9bbe84a2` | expected_resolution | 覆盖 | 并存 |
| `10e09553` | conflict_type | 时效 | 无 |
| `10e09553` | expected_resolution | 覆盖 | 并存 |
| `42ec0761` | conflict_type | 时效 | 否定 |
| `0977f2af` | expected_resolution | 覆盖 | 并存 |
| `89941a94` | expected_resolution | 覆盖 | 并存 |