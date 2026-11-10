# M3 汇总（B / C2 / D，154 确定性题 + 168）

> 口径固定：reader `deepseek-flash`、embedding `Qwen3-Embedding-8B`、判分官方移植、预算 4k、
> top-6、1 次/题（温度 1.0）。**不进官方 leaderboard**；只报同配置下的相对结果。

## 1. 三级对照（154 道确定性题）

| 臂 | 输入 | 压缩 | 准确率 | 相对 B |
|---|---|---|---|---|
| **B**（官方基线） | a11y 切片（radius=1，官方原文，不去重） | 无 | **53.9%**（83/154） | — |
| **C2**（我方压缩，a11y-only） | 同 B 的切片 | **L0 行级去重** + 4k 组装 | **57.1%**（88/154） | **+3.2pp** |
| **D**（完整轨迹） | 单 state（URL+action+thought+L0 增量） | L0 + 4k 组装 | **64.9%**（100/154） | **+11.0pp** |

解读：
- **压缩层贡献约 +3.2pp**（B → C2，输入模态不变）；
- **信息面贡献约 +7.8pp**（C2 → D，加入 action/thought 与 state 级组织）；
- D 相对 B 的配对检验：配对差 +11.0pp，置换检验 **p = 0.0116**（显著）。

## 2. 检索单元粒度对照（D 内部）

| D 变体 | 准确率 | 配对差 vs B | p |
|---|---|---|---|
| 单 state | 64.9% | +11.0pp | 0.0116 |
| state + 邻居（radius=1） | 64.3% | +10.4pp | 0.0205 |

两者差 0.6pp → **D 的优势不是检索粒度造成的**，而是 L0 与 action/thought 带来的信息质量。

## 3. 168 题（154 确定性 + 14 judge）

| 臂 | 准确率 | 分母 |
|---|---|---|
| B | 53.3% | 165（3 题 judge 输出无法解析，已排除） |
| D | 63.6% | 165 |
| 配对差 | +10.3pp | p = 0.0193 |

- judge：`deepseek-flash`，系统 prompt + rubric 冻结，sha256 = `24682689c75f2290b8803c5dae1a6db0b4d0a2c7f402250952ba470dd8ac6640`；
- 缺失题：`2cc1b9ca`、`910135bb`、`ea361b20`（不计 0，从分母剔除）。

## 4. 关键修正（此前低分数字作废）

- 修复前 B = 9.7%：`max_tokens=1024` 导致 reasoning 模型空答案（10 题里 7 题空）+ 判分未提取 `\boxed{}`（官方 harness 会先 `extract_boxed_answer`）；
- 修复后 B = 53.9%：`max_tokens` 8192（空答案再翻倍重试）、判分前提取 boxed 并剥离 `\text{}`；
- **以修复后的数字为准**，之前的 9.7% / 13.6% 作废。

## 5. 局限

1. 只有 1 次/题（无采样抖动估计）；小差异（< 3pp）不可靠。
2. 154 题单题翻转 ≈ 0.65pp；配对检验用 sign-flip 置换 10,000 次。
3. A/A 噪声底（20 题 × 10 次）：配对 |Δ| 均值 6.3pp——**C2 的 +3.2pp 小于噪声底**，只能作为方向性证据；D 的 +11.0pp 超过噪声底且 p<0.05。
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
  --b-ref data\eval\b_arm_154_run2.json --out data\eval\d_arm_154_neighbor.json --md-out docs\d_arm_154_neighbor.md
# 168（154 + 14 judge）
.venv\Scripts\python.exe scripts\eval_168_judge.py
```
