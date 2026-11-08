# knowledge-update 78 题标注协议（M0 交付物）

> 版本：v2（二次修正，撤回首版「8/72 日期方向相反」）｜日期：2026-11-07｜配套：`DATASET_LICENSES.md`
> 主集：LongMemEval-S（`longmemeval_s_cleaned.json`，revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`）
> 本协议产出的是**层 1 主指标的 gold**，且**分三层**：层 1a 现行值题 / 层 1b 回溯题 / 层 1c 拒答题。

---

## 1. 本协议要解决的问题

层 1 的主指标是「记忆注入后，回答是否仍在用已被更新的旧事实」。

但 LongMemEval 官方**只给 `answer`（新值），不给「旧值」标注，也不给逐条 evidence 结构**（实测：`answer` 是标量，78 题中 76 个 str + 2 个 int）。

所以必须自建 gold。**而这个 gold 的可靠性，直接决定层 1 主指标的可信度** —— 本协议的全部内容都服务于这一点。

> ⚠️ **自建 gold 时最容易漏的一层**：官方 `answer` 并不总是「当前值」——
> 有 7 道题的 `answer` 是**旧值**（问句带 `initially / previous / before / first N months` 这类回溯限定词）。
> **这 7 道不能按「答案是新值」处理**，否则会把层 1 的分母与指标方向全部搞反。详见 §2。

---

## 2. 关键事实：标注对象只有 2 个 session，但「旧→新」不能靠日期判定

实测（本地解析 `longmemeval_s_cleaned.json`，revision `98d7416c`）：

- 78 题 knowledge-update 每题有 **恰好 2 个 gold session**（`answer_session_ids` 长度为 2，100%）；
- 这 2 个 session 的 id 前缀 **100% 是 `answer_*`**，即 benchmark 合成的用户事实 session；
- 其余约 46 个 session 是 ShareGPT / UltraChat / 合成闲聊构成的**干扰项** —— 它们决定召回难度，但**不进入标注**。

> **标注只需读 2 个 session，不需要读 48 个。** 这一点成立。

### ⚠️ 首版结论已撤回：「8/72 题日期方向与语义相反」**不成立**（2026-11-07 二次实测修正）

**错因**：首版用**日期**（`haystack_dates`）判新旧。重跑改为**按 haystack 数组索引顺序**判（= 会话在对话流中的出现顺序），并把日期比较改成**含时刻**比较。两处都错了，所以整批结论要重写。

**按索引顺序的实测分布**（严格匹配：仅 user 消息 + token 边界整短语命中 + answer ≤6 token）：

| 判定 | 题数 | 占比 | 含义 |
|---|---|---|---|
| answer 唯一在**较晚索引** session | 49 | 62.8% | 现行值题（问当前状态） |
| answer 唯一在**较早索引** session | 7 | 9.0% | **回溯型问句**（问旧值） |
| 两边都有（BOTH） | 2 | 2.6% | 需人工 |
| 匹配不上（NEITHER） | 20 | 25.6% | 含 6 道拒答变体 → **14 道需人工** |

**日期序 vs 索引序（全量 78 题，含时刻）**：**77 题一致，仅 1 题相反**。

**首版那 8 道反例的真实构成**（逐题读原文后重判）：

| 判定 | 题数 | 题号 | 依据 |
|---|---|---|---|
| **回溯型问句**（问旧值，答案落在较早索引） | 7 | `07741c44` `50635ada` `e66b632c` `0ddfec37` `dfde3500` `9bbe84a2` `0977f2af` | 问句带明确回溯限定词：`initially` / `previous … before` / `first three months` / `before getting the Air Fryer`。**问的就是旧值，不存在「时间优先选错」。** |
| **真·日期反序** | 1 | `618f13b2` | answer=`six` 在 17:45 的 `_2`；`four times` 在 22:16 的 `_1`。唯一一处 `haystack_dates` 与语义方向相反。 |
| **匹配器假阳性** | 1 | `42ec0761` | answer=`Yes`（单 token）；首版宽松匹配命中较早 session 里的 `Yes, Google Drive provides…`（assistant 文本）。严格 user-only 匹配下该题应为「匹配不上」。 |

**替换首版的三条结论**

1. **新旧方向由「haystack 数组索引顺序」决定**，`haystack_dates` 只在 1/78 题上与它相反。首版「日期方向会出错、8/72 反向」的说法**作废**。
2. **answer 值匹配收紧后可用，且自动定位率比首版更高**：宽松匹配器 25 道「两边都有」里 17 道是假阳性 —— 78 题里 **38 题的 answer 归一化后只有 1 个 token**（多为数字）。收紧后 **56/78 题可自动定位**（49 较晚索引 + 7 较早索引），另 6 道拒答变体可自动识别，**仅 16 题需人工**（14 NEITHER + 2 BOTH）。
3. **「时间优先 vs 来源可信度」在主集上没有干净区分度；主集能暴露失败，但不能隔离策略**（见下）。

### ⚠️ 另一个必须先剔除的坑：78 题里有 6 道是**拒答变体**

`_abs` 后缀 = abstention（拒答）题，answer 是「The information provided is not enough. You mentioned …」，且在数据里 `question_type` 同样标成 `knowledge-update`：

```
6aeb4375_abs  031748ae_abs  2698e78f_abs
2133c1b5_abs  0ddfec37_abs  f685340e_abs
```

每道都有**同名非 abs 版**（同一 session 集下的「可答 / 拒答」成对）。
**这 6 道对过期事实率是无信息的**（正确拒答和答错都不命中 stale value），留在分母里只会稀释指标。

> **层 1 的真实可判题数 = 78 − 6 = 72。**
> （顺带解释：官方 README 说 5 大能力含 abstention，但 `question_type` 只有 6 个值 —— **拒答是通过 `_abs` 后缀编码的，不是独立题型**。）

### ⚠️ 最深一层后果：不是「时间优先测不了」，而是「主集上没有区分度」

首版写的是「LongMemEval 的新旧语义由内容决定，不由 `haystack_dates` 决定 → 时间优先只能在 zh30 上测」。
**结论方向保留，理由作废。** 主集上「时间优先 vs 来源可信度」没有干净区分度，但真正的原因有三条：

1. **来源可信度在主集上零方差** —— 156 个 gold session **100% 同源族 `answer_*`**（benchmark 合成的用户事实 session）。冲突两侧的来源按构造完全相同，**「来源可信度分级」这个策略在主集上根本没有可分性**，拿它当对照臂是无效对照。
2. **时间优先在现行值题上近乎必胜（构造偏置）** —— 49 道现行值题的答案按构造就放在较晚索引，「选较晚的」几乎必对。这测出来的是**数据集构造的投影**，不是策略证据。
3. **时间优先在回溯题上必败（题型效应）** —— 回溯题问的就是旧值，取新值是错的。但这考的不是「冲突裁决策略」，而是「**回溯意图识别**」。

> **结论：「时间优先 vs 来源可信度」在主集上无区分度，必须移到自建 zh30，且 zh30 必须刻意构造反向时间戳（见 `annotation-schema-zh30.md`）。**
>
> **但主集不是没有价值** —— 7 道已知回溯题（人工确认后可能更多）考的是一条**真实能力**：
> 读到 `initially / previous / before / first three months` 这类回溯限定词时，能否取到旧值。
> **「回溯意图识别」这条消融轴在主集上可测、有区分度、且面试里讲得清楚**，比「时间优先 vs 来源可信度」更值得作为主集消融项。
>
> **由此推出层 1 必须分三层报**（现行值题 / 回溯题 / 拒答题），不能一刀切成一个 N=72 的总一致率 —— 否则回溯题的低分会把现行值题的真实水平盖掉，反之亦然。见 §5。


---

## 3. 标注产出：字段 schema

每题一行，落在 `data/annotations/ku78.jsonl`：

| 字段 | 类型 | 取值 | 说明 |
|---|---|---|---|
| `question_id` | str | LongMemEval 原生 id | 主键 |
| `question` | str | 原样 | 只读，不改 |
| `query_form` | enum | `current` / `retrospective` / `abstention` | **问句形态（新增，必填）**。`current`=问当前状态；`retrospective`=问旧值（问句含 `initially/previous/before/first N months` 等回溯限定词）；`abstention`=该拒答。**这一列决定层 1 的分母分层，见 §5。** |
| `new_value` | str | 自标（或官方 answer） | **语义当前值**。current 题通常等于官方 answer；retrospective 题是**较晚 session 的当前值**。⚠️ v3 起不再定义为「官方 answer 只读」——该定义与 §2「retrospective 的 answer 是旧值」自相矛盾，pilot 已暴露 |
| `official_answer` | str | 只读 | 官方 `answer` 原样，仅用于追溯，不参与指标计算 |
| `official_answer_role` | enum | `current` / `old` / null | 官方 answer 是当前值（current 题）还是旧值（retrospective 题）；abstention 为 null |
| `official_answer_session_index` | int | `0` / `1` / null | 官方 answer 所在 gold session 的**相对索引**（0=较早，1=较晚）；abstention 为 null |
| `stale_value` | str / null | 自标 | 旧事实的**具体值**（不是整句）。**null = 无旧值（首次发生）**：例 `22d2cb42`（旧状态是"还没送修"）、`5c40ec5b`（旧状态是"还没见面"）——候选店名/计划不算旧值。`stale_value=null` 的题不参与"过期事实率"计算 |
| `stale_source_session_id` | str | `answer_*` | 旧值所在 gold session id |
| `new_source_session_id` | str | `answer_*` | 新值所在 gold session id |
| `session_order_source` | enum | `answer_match_index` / `manual` | **新旧 session 的判定依据**。自动 = answer 严格匹配 + **haystack 索引顺序**；人工 = 逐题确认。**日期不作为判定依据**（77/78 与索引一致，1/78 相反，详见 §2）。 |
| `gold_session_index` | int | `0` / `1` / null | **当前值**所在 gold session 的相对索引（0=较早，1=较晚）。⚠️ v3 起不再定义为「官方 answer 所在」——对 retrospective 题两者不同（官方 answer 在较早=0，当前值在较晚=1）；abstention 为 null |
| `stale_value_is_placeholder` | bool | `true` / `false` | 旧值是否为**占位词**（例：`5a4f22c0` 的 assistant 表格里写 `Old Company`，不是具体公司名）。true 时该题在层 1a 聚合中**单列或剔除**，不得静默算 0 |
| `is_abstention` | bool | `true` / `false` | `_abs` 拒答变体标 `true`，**这类题不进入层 1 分母** |
| `conflict_type` | enum | `时效` / `语义` / `偏好反转` / null | 冲突性质；abstention 题可为 null |
| `expected_resolution` | enum | `覆盖` / `并存` / `标失效` / `升级人工` / null | 记忆层应采取的裁决；abstention 题可为 null |
| `entity` | str | 自由文本 | 被更新的属性名（如「个人 5K 最好成绩」） |
| `match_mode` | enum | `exact` / `normalized` / `fuzzy` / null | 人工确认的匹配方式，供阈值敏感性分析用；abstention 题可为 null |
| `note` | str | 自由文本 | 歧义、无法判定等 |

**每题必须能定位到一句原文**，使「stale_value 出现在回答里」这件事可被第三方复核。

---

## 4. 标注流程

### Step 1 — 取题（脚本）
按 `question_type == 'knowledge-update'` 过滤出 78 条，输出 `question_id / question / answer / answer_session_ids / 两个 gold session 的完整消息与时间戳`。

### Step 2 — 预填候选（脚本，半自动）

**Step 2a：定位「answer 所在 gold session」+ 判问句形态**（用官方 `answer` 值匹配，**严格规则**）

1. 只在两个 gold session 的 **user 消息**里找，不看 assistant 回复；
2. 做 **token 边界整短语命中**（小写、去标点、压空格后按 token 序列比对）；
3. answer 归一化后 **>6 token 时不自动判定**（长答案几乎必然跨句误命中）；
4. 命中**唯一一侧** → 记 `gold_session_index` 与 `session_order_source = answer_match_index`；
5. 两边都命中 / 都没命中 → **交人工**，`session_order_source = manual`；
6. **判 `query_form`**（脚本给候选，人工确认）：问句命中回溯限定词（`initially|previous|before|former|used to|prior|first N months|earlier`）→ `retrospective`；`_abs` 后缀 → `abstention`；其余 → `current`。
   > ⚠️ 回溯限定词**可能指非时间实体**（如 `my previous company`、`my former manager`）—— 这类要人工改判为 `current`，不要按关键词一刀切。

> **实测自动定位率（严格规则，按索引顺序）**：
>
> | 状态 | 题数 | 处理 |
> |---|---|---|
> | 自动定位到 answer 所在 session + `query_form=current` | 49 | 直接进 gold |
> | 自动定位到 answer 所在 session + `query_form=retrospective` | 7 | 直接进 gold，**但需人工确认问句形态** |
> | `_abs` 自动识别 `abstention` | 6 | 进层 1c，**不进层 1a/1b 分母** |
> | BOTH / NEITHER 待人工 | 16 | **人工工时从首版的 28 题降到 16 题** |

**Step 2b：抽取候选值**
从两个 gold session 的 user 消息中抽取含数字或专有名词的短句，按 `entity` 关键词做粗对齐，生成 `stale_value` / `new_value` 的**候选对**。
> 候选一律视为不可信，必须逐条确认或改写。

> ⚠️ **`retrospective` 题的 stale/new 角色与 `current` 题相反**：
> `current` 题里 answer = **新**值、`stale_value` 是较早索引那一侧；
> `retrospective` 题里 answer = **旧**值（即 `stale_value`），而**新值在较晚索引那一侧**。
> 填错方向会让层 1b 的过期事实率完全反向 —— 这是本协议最容易出错的一处。

### Step 2.5 — Pilot（先做，不要直接批量标）

**先标 10 题 pilot**，覆盖下列五种判定各若干：

| 覆盖类型 | 建议题数 | 取法 |
|---|---|---|
| `current`（现行值题） | 4 | 从 49 道自动定位题里取，其中至少 1 道是 answer 为**多 token** 的长答案（检验匹配器在长答案上的稳定性） |
| `retrospective`（回溯型问句） | 3 | 从 7 道已知回溯题里取，覆盖三种限定词：`initially` / `previous … before` / `first N months` |
| 回溯限定词**指非时间实体** | 1 | 如 `my previous company` / `my former manager` 类（`5a4f22c0` `ba61f0b9`），**检验关键词一刀切会不会误判** |
| `abstention`（拒答变体） | 1 | 任取 `_abs` |
| BOTH / NEITHER（流程压力） | 1 | 从 16 道待人工题里取 |

| 记录项 | 目的 |
|---|---|
| 每题实际耗时 | 估算总工时（首版估 78 题，**实际人工只有 16 题**，工时口径要改） |
| 歧义类型与频次 | 决定是否要补 schema 字段或补定义 |
| schema 是否需改 | **在批量标之前定死**，否则 W2 会返工 |
| `query_form` 判定是否可靠 | 回溯限定词误判率 —— 直接决定层 1a/1b 分层的可信度 |

pilot 通过后才批量标剩余题。**若 pilot 显示 schema 不够，改 schema 后重新 pilot，不要硬标。**

### Step 3 — 人工确认（人工）
读两个 gold session：
- **先定 `query_form`**（`current` / `retrospective` / `abstention`）—— 看问句问的是当前状态还是旧值；
- 确认 `entity`（被更新的属性）；
- 确认 `stale_value`（旧值）与 `new_value`（新值），二者必须指向**同一个属性**；
- 定 `conflict_type` 与 `expected_resolution`；
- 定 `match_mode`：该值能否被精确匹配（`exact`）、需归一化（`normalized`）、还是只能模糊匹配（`fuzzy`）。

> ⚠️ **不得用日期定新旧** —— 日期在 77/78 题上与索引顺序一致，但那只是巧合性的一致；唯一反例 `618f13b2` 证明日期会错（`six` 在 17:45、`four times` 在 22:16）。
> **判定依据统一用「answer 出现在哪个 gold session」+「该 session 在 haystack 中的索引」。**

### Step 4 — 判定规则固化（脚本）
回答文本 → 归一化 → 匹配 `stale_value`：
1. **exact**：归一化后子串命中；
2. **normalized**：去标点 / 大小写 / 单位后命中；
3. **fuzzy**：token F1 ≥ 阈值（默认 0.8）。

命中即判为「该题使用了过期事实」。

### Step 5 — 阈值敏感性分析（脚本）
在 fuzzy 阈值 **0.7 / 0.8 / 0.9** 三档下分别计算过期事实率，**报告结论是否翻转**。
> 这是「自标注 gold 可不可信」的关键一环：如果 0.7 与 0.9 给出相反结论，说明判定规则不稳健，必须改规则而不是改数字。

### Step 6 — 复核（见 §6）

---

## 5. 指标定义（最终口径）

**层 1 必须分三层报，不能一刀切成一个总一致率。** 分层依据是 §2 实测出来的 `query_form`：

| 层 | 问句形态 | 分母 | 已知规模（自动定位） | 报什么 |
|---|---|---|---|---|
| **1a** | `current` —— 问**当前**状态 | N_a | **≥ 49**（另有 16 题待人工后再分配） | 过期事实率、与标注协议的一致率 |
| **1b** | `retrospective` —— 问**旧**值 | N_b | **≥ 7**（同上，待人工后再分配） | 回溯一致率（取到旧值才算对） |
| **1c** | `abstention` —— 该拒答 | N_c = **6** | 6 道 `_abs` | abstention 指标（该拒答而答 / 不该拒答而答），**单列，不进 1a/1b 分母** |

**N_a + N_b = 72**（78 题 − 6 道 `_abs` 拒答变体；剔除理由见 §2）。
若个别题人工判定为不可判，**从对应层分母剔除并在报告里列出被剔除的 question_id**，不得静默丢弃。

- **层 1a 过期事实率** = 回答命中 `stale_value` 的题数 / N_a
- **层 1a 与标注协议的一致率** = 系统裁决与 `expected_resolution` 一致的题数 / N_a
- **层 1b 回溯一致率** = 回答取到**旧值**（`answer`）的题数 / N_b
- **层 1c abstention** = （该拒答却给出答案的题数 + 不该拒答却拒答的题数）分别报 / N_c
- **按事实类型分列**：时效 / 语义 / 偏好反转 三类分别报（在层 1a 内）

> ⚠️ **「过期事实率」只在层 1a 计算。** 在层 1b（回溯题）上，「使用更新事实」是**正确答案**而不是过期事实 —— 把它算进过期事实率会把分母污染成反向指标。
>
> ⚠️ **不合并成一个总一致率。** 回溯题的一致率天然低于现行值题（需要额外的回溯意图识别能力），合并后现行值题的真实水平会被盖掉，反之亦然。三层必须并排呈现。

> ⚠️ **不使用「裁决准确率」这个名称** —— 本 gold 为单人自标注，不是独立 gold。指标名一律用「**与标注协议的一致率**」，并在报告首屏写明「gold 由单人标注，无第二人类标注者」。

> ⚠️ **「时间优先 vs 来源可信度」不在主集的消融范围内** —— 主集上来源可信度零方差（156/156 gold session 同源族 `answer_*`）、时间优先在层 1a 近乎必胜（构造偏置），**这一对轴无区分度**，移到自建 zh30 且须构造反向时间戳（§2 末、§9.2）。
>
> ✅ **主集上真正可测且有区分度的消融轴是「回溯意图识别」**（层 1b：读到 `initially/previous/before` 时能否取旧值）。这取代「时间优先 vs 来源可信度」成为主集消融项。

---

## 6. 标注可信度：三件套（缺一不可）

| # | 做什么 | 怎么做 | 报什么 |
|---|---|---|---|
| 1 | **自重复一致性** | 间隔 ≥ 7 天，对随机 **16 题（占层 1 分母 72 的 22%）** 重标，与第一次比 | 两次标注的一致率 |
| 2 | **跨模型交叉标注** | 用**与主 Judge 不同的另一个模型**独立标同样 16 题 | 交叉一致率 |
| 3 | **口径降级** | 无第二人类标注者时的措辞纪律 | 见下 |

**固定措辞（写进报告首屏，不得改写）**

> 单人工标注 + 自重复一致性检查 + 跨模型交叉检查；**无第二人类标注者**。

> ⚠️ **不得写成「双人标注」** —— 跨模型交叉检查**不是第二个人**，它是机器对机器协议可复现性的检验。
> 措辞一旦写成「双人」，任何懂行的面试官追问一句「第二个人是谁」就穿帮。

**第 2 条不违反「冻结 Judge」纪律**：那约束的是**评测阶段**的判分器；交叉标注属于**标注阶段**，用的模型与主 Judge 不同正是交叉验证的意义。

**若自重复一致率本身偏低**（例如 < 80%），说明问题在**标注协议**而不是模型 —— 此时应先改协议（补定义、补示例），再重标，**不得直接调数字**。

---

## 7. 复核记录表（随协议一起提交）

| 字段 | 值 |
|---|---|
| 标注者 | （单人） |
| 标注轮次 | 第 1 轮日期 / 第 2 轮日期（间隔 ≥ 7 天） |
| 复核题数 | 16 / 72 |
| 自重复一致率 | （待填） |
| 交叉模型 | （待填：模型名 + 版本） |
| 交叉一致率 | （待填） |
| fuzzy 阈值 | 默认 0.8 |
| 敏感性结论 | 0.7 / 0.8 / 0.9 三档结论是否一致 |
| 争议题清单 | question_id + 争议原因 |

---

## 8. 78 题清单（已从 revision `98d7416c` 实测导出）

```
  - `6a1eabeb` `6aeb4375` `830ce83f` `852ce960` `945e3d21` `d7c942c3` `71315a70` `89941a93`
  - `ce6d2d27` `9ea5eabc` `07741c44` `a1eacc2a` `184da446` `031748ae` `4d6b87c8` `0f05491a`
  - `08e075c7` `f9e8c073` `41698283` `2698e78f` `b6019101` `45dc21b6` `5a4f22c0` `6071bd76`
  - `e493bb7c` `618f13b2` `72e3ee87` `c4ea545c` `01493427` `6a27ffc2` `2133c1b5` `18bc8abd`
  - `db467c8c` `7a87bd0c` `e61a7584` `1cea1afa` `ed4ddc30` `8fb83627` `b01defab` `22d2cb42`
  - `0e4e4c46` `4b24c848` `7e974930` `603deb26` `59524333` `5831f84d` `eace081b` `affe2881`
  - `50635ada` `e66b632c` `0ddfec37` `f685340e` `cc5ded98` `dfde3500` `69fee5aa` `7401057b`
  - `cf22b7bf` `a2f3aa27` `c7dc5443` `06db6396` `3ba21379` `9bbe84a2` `10e09553` `dad224aa`
  - `ba61f0b9` `42ec0761` `5c40ec5b` `c6853660` `26bdc477` `0977f2af` `6aeb4375_abs`
  - `031748ae_abs` `2698e78f_abs` `2133c1b5_abs` `0ddfec37_abs` `f685340e_abs` `89941a94`
  - `07741c45`
```

### 每题的 session 规模与 gold 前缀（实测）

| question_id | haystack session 数 | 其中 `sharegpt_*` | gold 前缀 |
|---|---|---|---|
| 6a1eabeb | 40 | 11 | answer |
| 6aeb4375 | 47 | 16 | answer |
| 830ce83f | 47 | 13 | answer |
| 852ce960 | 39 | 9 | answer |
| 945e3d21 | 48 | 13 | answer |
| d7c942c3 | 49 | 17 | answer |
| 71315a70 | 53 | 16 | answer |
| 89941a93 | 51 | 10 | answer |
| ce6d2d27 | 51 | 14 | answer |
| 9ea5eabc | 53 | 18 | answer |
| 07741c44 | 50 | 12 | answer |
| a1eacc2a | 44 | 6 | answer |
| 184da446 | 42 | 8 | answer |
| 031748ae | 46 | 10 | answer |
| 4d6b87c8 | 52 | 14 | answer |
| 0f05491a | 45 | 10 | answer |
| 08e075c7 | 45 | 8 | answer |
| f9e8c073 | 53 | 17 | answer |
| 41698283 | 45 | 14 | answer |
| 2698e78f | 48 | 12 | answer |
| b6019101 | 49 | 14 | answer |
| 45dc21b6 | 49 | 14 | answer |
| 5a4f22c0 | 49 | 15 | answer |
| 6071bd76 | 46 | 5 | answer |
| e493bb7c | 51 | 11 | answer |
| 618f13b2 | 49 | 8 | answer |
| 72e3ee87 | 51 | 11 | answer |
| c4ea545c | 46 | 13 | answer |
| 01493427 | 47 | 8 | answer |
| 6a27ffc2 | 51 | 13 | answer |
| 2133c1b5 | 51 | 21 | answer |
| 18bc8abd | 44 | 11 | answer |
| db467c8c | 48 | 15 | answer |
| 7a87bd0c | 48 | 10 | answer |
| e61a7584 | 50 | 12 | answer |
| 1cea1afa | 49 | 14 | answer |
| ed4ddc30 | 46 | 7 | answer |
| 8fb83627 | 44 | 9 | answer |
| b01defab | 50 | 13 | answer |
| 22d2cb42 | 48 | 14 | answer |
| 0e4e4c46 | 49 | 12 | answer |
| 4b24c848 | 51 | 14 | answer |
| 7e974930 | 47 | 13 | answer |
| 603deb26 | 48 | 12 | answer |
| 59524333 | 44 | 13 | answer |
| 5831f84d | 40 | 8 | answer |
| eace081b | 47 | 17 | answer |
| affe2881 | 44 | 13 | answer |
| 50635ada | 48 | 10 | answer |
| e66b632c | 47 | 11 | answer |
| 0ddfec37 | 50 | 17 | answer |
| f685340e | 41 | 6 | answer |
| cc5ded98 | 53 | 20 | answer |
| dfde3500 | 47 | 10 | answer |
| 69fee5aa | 49 | 15 | answer |
| 7401057b | 47 | 15 | answer |
| cf22b7bf | 55 | 12 | answer |
| a2f3aa27 | 44 | 10 | answer |
| c7dc5443 | 46 | 12 | answer |
| 06db6396 | 51 | 15 | answer |
| 3ba21379 | 44 | 10 | answer |
| 9bbe84a2 | 48 | 10 | answer |
| 10e09553 | 45 | 10 | answer |
| dad224aa | 48 | 13 | answer |
| ba61f0b9 | 45 | 14 | answer |
| 42ec0761 | 48 | 14 | answer |
| 5c40ec5b | 51 | 16 | answer |
| c6853660 | 46 | 9 | answer |
| 26bdc477 | 48 | 16 | answer |
| 0977f2af | 44 | 10 | answer |
| 6aeb4375_abs | 46 | 7 | answer |
| 031748ae_abs | 52 | 14 | answer |
| 2698e78f_abs | 46 | 9 | answer |
| 2133c1b5_abs | 50 | 18 | answer |
| 0ddfec37_abs | 45 | 11 | answer |
| f685340e_abs | 43 | 6 | answer |
| 89941a94 | 46 | 12 | answer |
| 07741c45 | 49 | 15 | answer |

---

## 9. 已知边界（必须写进报告的局限章节）

1. **gold 为单人自标注**，无第二人类标注者；因此指标命名为「与标注协议的一致率」而非「准确率」。
2. **主集上「时间优先 vs 来源可信度」无区分度**（§2）：来源可信度零方差（156/156 gold session 同源族 `answer_*`）、时间优先在层 1a 近乎必胜（构造偏置）。该轴移到自建 zh30，且 zh30 必须构造反向时间戳 case。**主集上的消融轴改为「回溯意图识别」。**
3. **78 题里 6 道是拒答变体**（`_abs`），已从层 1a/1b 分母剔除（N_a + N_b = 72）。剔除清单必须写进报告，不得静默丢弃；但**层 1c 的 abstention 指标仍要单独报**，不得从所有报告里消失。
4. **自动定位率 72%（56/78）**：严格 answer 匹配 + 索引顺序后，49 道现行值题与 7 道回溯题可自动定位，另 6 道 `_abs` 自动识别，**仅 16 题需人工**（BOTH 2 + NEITHER 14）。自动预填只是起点，不是结论。
5. **stale_value 是「具体值」而非完整语义**；若旧值在回答中以近义改写出现，exact / normalized 判定会漏判 —— 这正是要做 fuzzy 阈值敏感性分析的原因。
6. **层 1a/1b 各自样本量小**：单题翻转即改变 1.39 个百分点（72 题口径），层 1b 只有 7 题起步、翻转可达 14 个百分点。结论必须给配对检验与噪声底，不得只报差值。
7. **`expected_resolution` 含有判断成分**：什么情况该「并存」而非「覆盖」，本身是设计选择。消融臂里会单列这一维度。
8. **官方基准不评测写入行为**，因此本协议产出的 gold 无法与任何公开写入基准对标。
9. **session 原文不进仓库**；本协议与 `ku78.jsonl` 只含自标字段与官方 id / answer，不含第三方会话文本。
10. **`query_form` 由关键词判定会有误判**（如 `my previous company` / `my former manager` 指向非时间实体）。层 1a/1b 的分母依赖这一列，因此 pilot 必须实测该列的误判率，并在报告中给出人工复核后的最终分布。
11. **首版「8/72 题日期方向与语义相反」已作废**（同日二次实测修正，§2）。若此前有任何文字沿用该口径，一律以本版 §2 的三分表为准。

---

## 10. v3 变更记录（2026-11-08，pilot10 后）

依据 `dataset/v1/pilot10-给DeepSeek的说明.md` 的 Q1–Q5，已核实数据后定稿：

| # | 变更 | 原因 | 依据 |
|---|---|---|---|
| 1 | `new_value` 语义改为「语义当前值」；新增 `official_answer` / `official_answer_role` / `official_answer_session_index` | §3 原「`new_value` = 官方 answer」与 §2「retrospective 的 answer 是旧值」自相矛盾；pilot 06/07/08 撞上 | pilot Q1 |
| 2 | `gold_session_index` 语义改为「**当前值**所在」；官方 answer 所在另用 `official_answer_session_index` | 对 retrospective 题两者不同（官方 answer 在较早=0，当前值在较晚=1） | pilot Q2 |
| 3 | 新增 `stale_value_is_placeholder` | `5a4f22c0` 的旧值是 assistant 表格里的占位词 `Old Company`（已核实 session `answer_b0f3dfff_1`，idx 7），不是具体公司名 | pilot Q4 |
| 4 | `conflict_type` / `expected_resolution` / `match_mode` 允许 `null` | abstention 题无冲突、无裁决 | pilot Q3 |
| 5 | 06（`07741c44`）的数据歧义**已排除**：官方 gold = `under my bed`（`answer_7e9ad7b4_1`，idx 7，"keeping them under my bed"）；`a few pairs hidden away in my closet` 指另外几双，不构成旧鞋的旧位置 | 已读两个 gold session 原文 | pilot Q5 |

**pilot10 回填结果**：10 行已按 v3 回填到 `dataset/v1/annotations-pilot10-v2.jsonl`，校验通过（`scripts/backfill_pilot10.py`）：
- current 6 题：`new_value` 均为官方 answer 归一化子串；
- retrospective 3 题：`stale_value` 均为官方 answer 归一化子串；
- abstention 1 题：`is_abstention=true`，其余字段 null；
- 非 abs 题的 `stale/new_source_session_id` 均属于 `answer_session_ids`。

**占位旧值题的处理约定**：`stale_value_is_placeholder=true` 的题**不进层 1a 主分母**，在报告里单列（列出 question_id 与原因），不静默算 0。

### v3.1 补充（同日晚，63 行批标后）

| # | 规则 | 说明 |
|---|---|---|
| 6 | `stale_value` 允许 `null`，表示**无旧值（首次发生）** | `22d2cb42`（未送修，`Rhythm Central` 只是候选）、`5c40ec5b`（未见面）。这类题不参与"过期事实率"，单列 |
| 7 | **复合答案题**：`new_value` 填**具体当前值**，不是布尔/比较结论 | `c4ea545c` → `four times a week`（不是 `Yes`）；`031748ae` → `5`（不是复合句）；`f685340e` → `every other week`。官方复合句仍完整保存在 `official_answer` |
| 8 | **双槽位问句**（同时问"刚上任时/现在"、"previously/now"）→ `query_form=current` | `031748ae`、`f685340e` 归 current；旧值仍记录在 `stale_value`。不留 `manual_needed` |
| 9 | `89941a94` 的 `gravel bike` 与原文 `new hybrid bike` 措辞不一致 | 官方 answer（`Yes. (You have a road bike too.)`）由 S1 的 road bike 支持，**答案成立**；保留 retrospective，在 `note` 标注措辞差异，不剔除 |

### v3.2 补充（MiniMax agent 交叉后，人工仲裁）

| # | 规则 | 依据 |
|---|---|---|
| 10 | **布尔事实的旧状态为 `No` 时填 `No`，不填 null**。`null` 只用于「该事实此前从未存在」 | `b01defab`：S1「读到一半暂时搁置」= 旧值 `No`；MiniMax 误判为 null。而 `22d2cb42`（未送修）、`5c40ec5b`（未见面）才是「从未存在」 |
| 11 | **问题时间窗优先于累计口径** | `5831f84d`：题目问 `in the past few weeks`，旧值取同口径的 `10`，不取同 session 的累计 `12` |

