# M2 记忆质量评测（V1 72 题 gold）

> 用 V1 的 72 题 gold 检验“系统自动判定”与人工标注的一致率；不新标、不改 gold。

| 指标 | 一致率 |
|---|---|
| query_form（回溯意图） | 0.9861 |
| conflict_type（冲突类型） | 0.8889 |
| expected_resolution（裁决） | 0.8472 |

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