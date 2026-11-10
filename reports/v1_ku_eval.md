# V1-KU 端到端问答评测（72 题）

> 口径：给 reader 看 A/B 两个 gold session + 问题，让它回答；1a = current（问当前值），1b = retrospective（问旧值，期望命中 `stale_value`）。
> **1c abstention 的 6 道不在 ku72 的 72 题 gold 里**（原始 78 题中的 `_abs` 变体被排除），本次未覆盖。
> 与 V2 主集的 QA 准确率不是同一口径，不可直接比。

## 两段式（当前实现，已产品化）

1. **意图判定**：先判 current / retrospective（同 M2 提示词）；
2. **条件回答**：按意图提示模型取当前值或旧值（retrospective 明确提示“取 A 段旧值”）；
3. **LLM judge**：判答案与期望值（current→`new_value`，retrospective→`stale_value`）是否等价。

| 指标 | 旧实现（单段 + 子串） | **两段式（judge）** | 变化 |
|---|---|---|---|
| 1a current 命中率 | 44.44% | **65.08%** | +20.6pp |
| 1b retrospective 命中率 | **0.00%**（0/9） | **77.78%**（7/9） | **+77.8pp** |
| 意图判定准确率 | —（未判） | 83.33% | — |

## 结论

1. **回溯 0/9 不是模型不会，而是评测/链路没告诉它“问的是过去”**：加上意图判定 + 条件提示后，回溯命中从 0 → 7/9。
2. **当前值 44.4% → 65.1%**：一部分来自“明确要求回答当前值”，一部分来自 judge 认出了等价表述（子串只作下界）。
3. **意图判定 83.3%**（低于 M2 的 98.6%，因为这里会话被截断、且没有 M2 的完整标注上下文）——说明“识别”本身仍有提升空间。
4. **产品化**：`memory/intent.py` 已接入聊天入口——retrospective 时自动注入系统提示，`memory_search` 带 `include_history=true` 取回失效历史值；trace meta 记录 `intent`。

## 局限

- 1c 拒答层未覆盖（72 题 gold 不含 `_abs` 题）；
- judge 有一定随机性；两段式多一次模型调用（意图判定）；
- 单次运行，结论以方向 + 量级为准。

## 可复现

```powershell
.venv\Scripts\python.exe scripts\v1_ku_eval.py --mode two-stage   # 两段式
.venv\Scripts\python.exe scripts\v1_ku_eval.py --mode single      # 旧实现对照
```
