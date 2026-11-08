# V1-KU pilot10 记录（schema v3 定稿）

> 标注者：单人（用户）；时间：2026-11-08。
> 标注文件：`dataset/v1/annotations-pilot10.jsonl`（原始）→ `dataset/v1/annotations-pilot10-v2.jsonl`（v3 回填，含 session 片段，**不入库**）。
> 回填与校验：`scripts/backfill_pilot10.py` → **validation: OK**。
> 协议：`docs/annotation-protocol-ku78.md` §3 + §10。

## 1. 结论

1. **10 行标注方向全部正确**：current 6 题的 `new_value` 都是官方 answer 的归一化子串；retrospective 3 题的 `stale_value` 都是官方 answer 的归一化子串；abstention 1 题字段齐全。
2. **分层一致性 9 / 10**：9 题与自动分层一致；**`6a1eabeb` 从 `manual_needed` 人工判为 `current`**（官方 answer `25:50` 是当前值，旧值 `27:12`）。
3. schema 的 Q1–Q5 已全部定稿为 **v3**（见 §3），pilot 材料与 72 题骨架均已按 v3 重跑。

## 2. 分母更新（pilot 后）

| 层 | 题目 | 说明 |
|---|---|---|
| 1a current | **50**（自动 49 + `6a1eabeb` 人工判入） | 其中 `5a4f22c0` 的旧值是占位词 `Old Company` → **不进 1a 主分母**，故 1a 有效分母 = **49** |
| 1b retrospective | **7** | 不变 |
| manual_needed | **15** | 16 − `6a1eabeb`（已判） |
| 1c abstention | **6** | 单列，不进 1a/1b |

> 72 = 50 + 7 + 15；1a 主分母 = 50 − 1（placeholder）= **49**，与协议「N_a ≥ 49」一致。剩余 15 道 manual 判层后需重算。

## 3. schema v3 决策（对应标注者 Q1–Q5）

| # | 问题 | 决策 |
|---|---|---|
| Q1 | retrospective 的 `new_value` 填什么 | **填语义当前值**（不是官方 answer）。新增 `official_answer`（官方原样）、`official_answer_role`（current/old）、`official_answer_session_index`（0/1） |
| Q2 | `gold_session_index` 指向哪个 session | **指向当前值所在**（0=较早，1=较晚）；官方 answer 所在另用 `official_answer_session_index`。对 retrospective：`gold_session_index=1`、`official_answer_session_index=0` |
| Q3 | abstention 的 null | 允许 `stale_value / gold_session_index / conflict_type / expected_resolution / match_mode` 为 null；schema 已注明 nullable |
| Q4 | `Old Company` 占位词 | 已核实：`answer_b0f3dfff_1` 的 assistant 表格里 Company 列写 `Old Company`，不是具体公司名。保留 `stale_value="Old Company"`、`match_mode=exact`，新增 `stale_value_is_placeholder=true`；该题**不进 1a 主分母**，报告单列 |
| Q5 | 06 的数据歧义 | 已核实：官方 gold = `under my bed`（`answer_7e9ad7b4_1`，idx 7，"keeping them under my bed"）；`a few pairs hidden away in my closet` 指**另外几双**，不构成旧鞋的旧位置。标注者的判断正确，无数据缺陷 |

## 4. 数据核实证据（逐题）

| # | id | 官方 answer | 旧值依据 | 当前值依据 |
|---|---|---|---|---|
| 01 | `5a4f22c0` | `TechCorp` | `_1`（idx 7）assistant 表格 `Old Company`（占位） | `_2`（idx 40）user："currently at TechCorp" |
| 02 | `6aeb4375` | `four` | `_1`："three different ones" | `_2`："four different ones" |
| 03 | `830ce83f` | `the suburbs` | `_1`：Chicago | `_2`：the suburbs |
| 04 | `852ce960` | `$400,000` | `_1`：$350,000 | `_2`：$400,000 |
| 05 | `945e3d21` | `Three times a week` | `_1`：twice a week | `_2`：three times a week |
| 06 | `07741c44` | `under my bed`（旧） | `_1`（idx 7）："keeping them under my bed" | `_2`（idx 30）："in a shoe rack" |
| 07 | `50635ada` | `Premier Silver`（旧） | `_1`（idx 19）："eligible for Premier Silver" | `_2`（idx 42）："just reached Premier Gold" |
| 08 | `0ddfec37` | `15`（旧） | `_1`（idx 18）："that's 15 autographed baseballs" | `_2`（idx 32）："added 20 autographed baseballs" |
| 09 | `6aeb4375_abs` | 拒答文本 | 无（abstention） | 无 |
| 10 | `6a1eabeb` | `25 minutes and 50 seconds (or 25:50)`（当前） | `_1`（idx 19）：27:12 | `_2`（idx 39）：25:50 |

## 5. 下一步

1. 批量标剩余 **62 题**（current 50 − 已标 6 + retro 7 − 已标 3 + 其余），按 v3 schema。
2. 判剩余 **15 道 manual_needed**（`dataset/v1/manual16.md` 去掉 `6a1eabeb`）。
3. 判层后重算 1a/1b；placeholder 题单列。
4. 16 题自重复（间隔 ≥7 天）+ 跨模型交叉复核；fuzzy 阈值敏感性（0.7/0.8/0.9）。
