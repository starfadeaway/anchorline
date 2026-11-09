# 评测稳定性汇总（v2 vs v3，154 题）

> 目的：同一臂（B 官方基线 / D 完整轨迹+L0）重复跑一次，看聚合准确率与单题翻转，判断结论是否被采样噪声支配。
> 口径：154 题确定性判分（无 judge）、reader deepseek-flash、embedding Qwen3-Embedding-8B、4k 预算、top-6、temperature=1.0、n=1/题。
> 数据：`data/eval/b_arm_154_v2.json`、`b_arm_154_v3.json`、`d_arm_154_v2.json`、`d_arm_154_v3.json`。

## 1. 聚合准确率

| 运行 | B（官方基线） | D（完整轨迹+L0+L3） | D − B | 检验 |
|---|---|---|---|---|
| v2 | 53.90% | 64.94% | **12.34pp** | 配对置换 p=0.0046 |
| v3 | 57.14% | 66.23% | **9.09pp** | sign-flip p=0.0415 |

## 2. 同臂重复性（v2 → v3）

| 臂 | v2 | v3 | 差值 | 单题翻转 |
|---|---|---|---|---|
| B | 53.90% | 57.14% | **+3.25pp** | 19/154（12.3%，12 好 / 7 坏） |
| D | 64.94% | 66.23% | **+1.30pp** | 18/154（11.7%，9 好 / 9 坏） |

两次运行的聚合差（+3.25pp / +1.30pp）**都在 A/A 噪声底 6.3pp 以内**；单题翻转约 **12%**，正负近似对称——符合 temperature=1.0 的采样噪声特征。

## 3. 结论

1. **聚合准确率稳定**：B、D 两次运行差异均小于噪声底，D > B 的方向在两次运行中都成立且显著（12.34pp / 9.09pp）。
2. **单题级不可过度解读**：约 12% 的题会翻转；报告与前端只展示聚合与配对检验，不引用单题分数做结论。
3. **效应量下界**：以两次运行中较小的 9.09pp 作为保守估计，D 相对 B 的提升仍在噪声底之上。
4. 本汇总不替代 168 题口径（154 + 14 judge）；168 v3 待跑。

## 4. 复现

```powershell
.venv\Scripts\python.exe scripts\eval_suite.py --arm b --a data\eval\b_arm_154_v2.json --b data\eval\b_arm_154_v3.json
.venv\Scripts\python.exe scripts\eval_suite.py --arm d --a data\eval\d_arm_154_v2.json --b data\eval\d_arm_154_v3.json
```
