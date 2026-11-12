# B 臂「按 State 分预算」（§42.2）

> 背景：B/C1 的检索单元是 radius=1 的 3-state 拼接（B median 49k、C1 median 40k 字符），
> 而 4k 预算下保头截断保住的是**最旧的 state**。实测 center 块起点在全串 27%–50% 处：
> 400 条样本里 center 还能见到的比例，cap=2666 时 7.8%、cap=16000 时 50.3% ——
> **回退到 16000 恢复了数字，但没有修掉「center 被丢」这个病。**

## 做法

在**组装期**（不改索引、不重建）把 3-state 文本重新分配预算：

- 所有 State 的 header（`State N (step N)` / `- URL` / `- Action` / `- AXTree:`）**全保留**；
- AXTree 按 center 优先分配：center 50%，其余平分剩余 50%（等价于「center 优先的 50/30/20」）；
- 总长不超过「4k 预算的字符数 − 外层包装约 400 字符」，截断处带 `…(截断)`；
- 找不到 center 时按中间段处理。

实现：`src/anchorline/evaluation/state_budget.py`（`parse_states` / `budget_state_text`）。

## 用法

```python
answer_baseline(reader, embedder, tbl, question, state_budget=True)
```

或环境变量 `ANCHORLINE_STATE_BUDGET=1`（默认关闭，需先做 A/B 验证效果）。

## 离线验证（已做）

- `tests/test_state_budget.py`：5 条（拆分、header 全保留、center 优先、截断标记、预算内 no-op）；
- `tests/test_arms_offline.py`：接入测试（3 个 header 全保留、token ≤ 4000）。

## 待做（需要一次真实 A/B）

在 B 的 154 题上对比：

1. `state_budget=False`（当前默认，旧行为）；
2. `state_budget=True`（本模块）；
3. 记录 `context_tokens`、`dropped`、准确率、精确符号翻转 p。

**只有 A/B 显示不劣于旧行为时，才把默认值改为开启**。不要仅凭设计直觉改默认——
2666 封顶实验就是「算式推出的改动未做 A/B」的直接教训。
