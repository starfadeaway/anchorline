# M3 汇总（B / C2 / D，154 确定性题 + 168）

> 口径固定：reader `deepseek-flash`、embedding `Qwen3-Embedding-8B`、判分官方移植、预算 4k、
> top-6、1 次/题（温度 1.0）。**不进官方 leaderboard**；只报同配置下的相对结果。

## 1. 三级对照（154 道确定性题）

| 臂 | 输入 | 压缩 | 准确率 | 相对 B |
|---|---|---|---|---|
| **B**（a11y 子集基线） | a11y 切片（radius=1，官方原文，不去重） | 无 | **53.9%**（83/154） | — |
| **C2**（我方压缩，a11y-only） | 同 B 的切片 | **L0 行级去重** + 4k 组装 | **57.1%**（88/154） | **+3.2pp（vs run2 的 B 53.9%，源 p=0.219；对比 B_run2_vs_C2（后者−前者））** |
| **D**（完整轨迹） | 单 state（URL+action+thought+L0 增量） | L0 + 4k 组装 | **64.9%**（100/154） | **+11.0pp** |

解读（本版修正为单变量分解）：
- **输入模态（完整轨迹 vs a11y-only，B 与 C1）**：−3.25pp，p=0.5224 —— 单独换成完整轨迹没有增益（单 state 口径）；
- **压缩（a11y-only，B 与 C2）**：−3.25pp，p=0.4049 —— 该模态下 L0 去重没有显著差异（单 state 口径）；
- **同一 C2 对照 run2 的 B（B_run2 → C2）**：+3.2pp、源文件 p=0.219（c2_arm_154.json 自报，随机置换 10000 次）。
  注意：2×2 里的 C2 行用的是 **run3 单 state 的 B 与 C2**（−3.25pp，p=0.4049，精确符号翻转）——**两者参照臂不同（run2 vs run3），不可互相验证**；C2 产物里的 p 与 2×2 的 p 本来就是两套检验。
- **压缩（完整轨迹，C1 与 D_neighbor）**：+7.14pp，**p=0.1263（不显著）** —— 旧 3-state 口径的 +10.39pp/p=0.0195 **同样不稳健**（少 1 题即跌破 0.05）；**口径修正让数字作废，但作废的是「显著」这个强度判断本身**——数字没错，错的是我们此前对它的信心；
- **检索粒度（单 state vs 3-state 邻域，D → D_neighbor）**：−1.95pp，p=0.7359 —— 粒度可忽略。

> **归因说明**：旧版「压缩 +3.2pp / 信息面 +7.8pp」把 `C1 → D` 当作单变量，但那一格同时变了
> L0 去重与检索粒度（3-state → 单 state），不能单独归因给压缩。正确的单变量对比是上面的四行；
> 结论是**压缩的收益依赖输入模态（交互效应）**，而粒度不是原因。D 相对 B：run2 口径 +11.0pp（p=0.0115）；run3 单 state 口径 **+5.84pp（p=0.2327，不显著）**——旧 run3 的 +9.09pp/p=0.0385 同样不稳健（D 少赢 1 题即 p=0.0807）；修正后 +5.84pp、p=0.2327——**作废的是「显著」这个强度判断，不是数字**。

> **批次口径说明（2026-11-12 修正）**：§1 的**表格**用 **run2**（B 53.9% / D 64.9%）；§1 下方的**解读**用 **run3 单 state**（B 60.39% / C1 57.14% / C2 57.14% / D 66.23%——C1/C2 只有 run3 一批，无法用 run2 对）。
> 因此同一份文档里「B」出现了两个不同的数：表格 53.9%（run2）与解读 60.39%（run3 单 state）——**不是可跨行相加的口径**，各自只与同段数字配对。C2 是单独一批。
> `d_arm_154_*.json` 产物以 **`b_arm_154_run2`** 为参考臂；而 `eval_2x2.py`（`m3_2x2.md`）默认用 **`b_arm_154_run3`**。
> 同一个 D 臂因此在两套报告里配了两个不同的 B —— 各自内部自洽，但**不能跨报告直接比较**。

## 2. 检索单元粒度对照（D 内部）

| D 变体 | 准确率 | 配对差 vs B | p |
|---|---|---|---|
| 单 state（run2） | 64.9% | +11.0pp | 0.0115 |
| state + 邻居（radius=1） | 64.3% | +10.4pp | 0.0195 |

两者差 0.6pp → **D 的优势不是检索粒度造成的**，而是 L0 与 action/thought 带来的信息质量。

## 3. 168 题（154 确定性 + 14 judge）

| 臂 | 准确率 | 分母 |
|---|---|---|
| B | 53.3% | 165（3 题 judge 输出无法解析，已排除） |
| D | 63.6% | 165 |
| 配对差 | +10.3pp | p = 0.0186（165 题，精确） |

- judge：`deepseek-flash`，系统 prompt + rubric 冻结，sha256 = `24682689c75f2290b8803c5dae1a6db0b4d0a2c7f402250952ba470dd8ac6640`；
- 缺失题：`2cc1b9ca`、`910135bb`、`ea361b20`（不计 0，从分母剔除）。

## 4. 关键修正（此前低分数字作废）

- 修复前 B = 9.7%：`max_tokens=1024` 导致 reasoning 模型空答案（10 题里 7 题空）+ 判分未提取 `\boxed{}`（官方 harness 会先 `extract_boxed_answer`）；
- 修复后 B = 53.9%：`max_tokens` 8192（空答案再翻倍重试）、判分前提取 boxed 并剥离 `\text{}`；
- **以修复后的数字为准**，之前的 9.7% / 13.6% 作废。

## 5. 局限

1. 只有 1 次/题（无采样抖动估计）；小差异（< 3pp）不可靠。
2. 单题翻转约 12%（对聚合准确率的净影响约 0.65pp）；配对检验用**精确符号翻转**（不依赖 numpy 版本）。
3. 噪声口径：采用**同臂复跑差**（B +3.25pp / D +1.30pp，154 题、同量纲）。旧版引用的「A/A 6.3pp」来自 `aa_pilot.json`（B 臂 20 题、17 题恒 0），只代表 B 臂题内不稳定率，不能代表 D 臂。按同臂复跑差：C2 的 +3.2pp 与复跑波动同量级（只能算方向性）；D 的 +11.0pp 明显高于复跑波动且 p<0.05。
4. 判分严格（官方 `norm_phrase_set_match`），"部分正确"判 0；B 诊断显示 12 道错题里 10 道是真答错，判分只压了 1–2 道。
5. 4k 预算用 `chars/4` 近似；a11y 文本实际约 1 char ≈ 1 token，真实注入可能超名义预算（三臂同口径，不影响相对比较，但绝对值会变）。

## 6. 复现

```powershell
# B（154）
.venv\Scripts\python.exe scripts\aa_pilot.py --limit 154 --n 1 --out data\eval\b_arm_154_run2.json
# C2（154）
.venv\Scripts\python.exe scripts\eval_c2_arm.py --limit 154
# D 单 state（154）
.venv\Scripts\python.exe scripts\eval_d_arm.py --limit 154 --n 1 --table v2_web_states_d `
  --b-ref data\eval\b_arm_154_run2.json --out data\eval\d_arm_154_run2.json --md-out reports\d_arm_154_run2.md
# D 邻居（154）
.venv\Scripts\python.exe scripts\eval_d_arm.py --limit 154 --n 1 --table v2_web_states_d_neighbor `
  --b-ref data\eval\b_arm_154_run2.json --out data\eval\d_arm_154_neighbor.json --md-out reports\d_arm_154_neighbor.md
# 168（154 + 14 judge）
.venv\Scripts\python.exe scripts\eval_168_judge.py
```

## 5. 混合检索的负结果（Y5：负面结果也写进主报告）

用**产品侧检索**（BM25 + 向量 + RRF + rerank）在同一 state 表上跑 154 题：**55.84% vs 纯向量 66.23%，
−10.4pp，p=0.0195**（多参照：vs run2 p=0.0488、vs neighbor p=0.0984，方向一致）。

结论：**主评测（B/C1/C2/D）保持纯向量 top-6**；产品 `memory_search` 的混合检索用于短事实文本（**该场景尚未对照验证**），
不能把评测数据上的结果外推到产品，反之亦然。详见 `reports/d_arm_154_hybrid.md`。

> **B 臂口径说明（2026-11-12 修正）**：B/C1/C2 的索引已改为**单 state**（--radius 0；B 每条 entry = center state 的 AXTree，median 15,998 字符，cap 16000），与 D（median 702）的检索单元粒度一致。旧 3-state 口径（median 49k/40k）会在保头截断时把 center 切掉——B 57.14→60.39、C1 53.90→57.14、C2 净值不变。按 2666 字符封顶经实测显著变差（43.51%，p=0.0011），不采用。B 只复刻官方 a11y 通道（官方另有 event/note 与改写查询），绝对准确率不代表官方基线全貌。详见 docs/b_c1_c2_single_state_experiment.md。
