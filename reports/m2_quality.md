> 样本量 n = 72；空预测数 n_empty_pred = 0

# M2 记忆质量评测（V1 72 题 gold）

> 用 V1 的 72 题 gold 检验“系统自动判定”与人工标注的一致率；不新标、不改 gold。

> **基线说明**：每个指标必须与「常数基线」（gold 众数占比）对照；零方差的 gold 字段（如 conflict_type=时效 72/72）
> 常数预测器即 100%，此类指标不构成能力指标。

> **词表修复后的重跑（2026-11-11）**：评测/盲标 prompt 已统一到协议词表（时效/语义/偏好反转/无；覆盖/并存/标失效/升级人工），重跑结果为上表。
> 结论：conflict_type 仍 0.8889、expected_resolution 0.8194（略降）——说明这两个指标的偏差**不只是词表错配**，模型的时效/覆盖判断本身也有偏差；
> 且两者均低于常数基线（100%），仍应视为「不可评测」而非能力指标。

> **两套口径**：严格 = gold 非空即计入；宽松 = 双方都非空才计入。

| 指标 | 严格一致率 | 宽松一致率 |
|---|---|---|
| query_form（回溯意图） | 0.9722 | 0.9722 |
| conflict_type（冲突类型） | 0.8889 | 0.8889 |
| expected_resolution（裁决） | 0.8194 | 0.8194 |

## 逐题差异（不一致项）

| qid | 字段 | gold | pred |
|---|---|---|---|
| `852ce960` | query_form | current | retrospective |
| `852ce960` | expected_resolution | 覆盖 | 并存 |
| `d7c942c3` | conflict_type | 时效 | 无 |
| `d7c942c3` | expected_resolution | 覆盖 | 并存 |
| `07741c44` | conflict_type | 时效 | 无 |
| `07741c44` | expected_resolution | 覆盖 | 并存 |
| `22d2cb42` | query_form | current | retrospective |
| `22d2cb42` | conflict_type | 时效 | 无 |
| `22d2cb42` | expected_resolution | 覆盖 | 并存 |
| `50635ada` | expected_resolution | 覆盖 | 并存 |
| `e66b632c` | expected_resolution | 覆盖 | 并存 |
| `0ddfec37` | conflict_type | 时效 | 无 |
| `0ddfec37` | expected_resolution | 覆盖 | 并存 |
| `dfde3500` | expected_resolution | 覆盖 | 并存 |
| `69fee5aa` | conflict_type | 时效 | 无 |
| `9bbe84a2` | expected_resolution | 覆盖 | 并存 |
| `10e09553` | expected_resolution | 覆盖 | 并存 |
| `42ec0761` | conflict_type | 时效 | 无 |
| `42ec0761` | expected_resolution | 覆盖 | 并存 |
| `0977f2af` | conflict_type | 时效 | 无 |
| `0977f2af` | expected_resolution | 覆盖 | 并存 |
| `89941a94` | conflict_type | 时效 | 无 |
| `89941a94` | expected_resolution | 覆盖 | 并存 |