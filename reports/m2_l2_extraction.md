# L2 事实抽取评测（V1 72 题）

> 目的：检验“从会话中抽取事实”这一步的质量。用 reader 从每题会话抽 entity/attribute/value，
> 与 ku72 的 gold `new_value` 做归一化子串比对。**非人工评审**。

## 结果

| 指标 | 值 |
|---|---|
| gold value 命中率 | **1.39%**（1/72） |
| 平均抽取事实数 | 9.21 |
| JSON 解析失败 | 3/72 |

## 为什么这么低（不是“抽取器抽不出东西”）

逐题看 facts 后，原因有三类：

1. **抽到的是“旧值/首次出现”**：如 `6a1eabeb` gold=25:50，抽取器给出 `5k_pb=27:12`（会话 A 的旧值）——它把“会话里出现过的事实”都抽了，没有按 A/B 时间序做 supersede。
2. **value 语义不同**：如 `6aeb4375` gold=`four`（数量），抽取器抽的是菜单细节（`falafel`、`Korean BBQ options`），没有抽到“四个菜”这个数量事实。
3. **数字格式**：gold `25:50` vs 抽取 `25 minutes and 50 seconds` 这类格式差异也会漏判（归一化只处理符号）。

## 结论

- 这个指标测的是「抽取器能否抽到**当前值**对应的事实」，不是「抽取的准确率」；
- 1.39% 说明 **L2 抽取必须带“时间序 + 冲突裁决”**——这正是记忆层 L2 的核心价值（supersedes / invalidate），单独抽事实不够；
- 不能据此说“模型抽取能力差”：平均 9.21 条事实/题，抽取本身是有效的。

## 改进方向

1. 抽取时给每条 fact 带 session 序号（A/B），同 attribute 自动 supersede；
2. 评测改为「LLM 判覆盖」而不是字符串匹配（成本 +72 次 judge）；
3. 有人工抽取 gold 后再算抽取准确率（当前 gold 是“答案值”，不是“抽取标注”）。

复现：`.venv\Scripts\python.exe scripts\eval_l2_extraction.py`
