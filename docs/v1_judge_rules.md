# V1-KU 判定规则（v1，已对 72 条标注自检）

> 代码：`src/anchorline/evaluation/v1_judge.py`；单测：`tests/test_v1_judge.py`
> 自检脚本：`scripts/audit_ku72_judge.py`；数据：`data/annotations/ku72.jsonl`

## 1. 三档定义

| 档 | 定义 | 用途 |
|---|---|---|
| `exact` | 小写 + 去标点 + **token 边界**子串命中 | 最严格，误判最少 |
| `normalized` | exact + 英文数字词转阿拉伯数字 + 去 `$`/千分位 | **默认档** |
| `fuzzy` | token 级 F1 ≥ 阈值（0.7/0.8/0.9） | 只作敏感性分析 |

## 2. 跳过与单列规则

- **跳过**（不进过期事实率）：`stale_value=null` 或 `stale_value_is_placeholder=true`，共 3 题：
  - `5a4f22c0`（stale = answer_b0f3dfff_1(第一个 gold session); new = answer_b0）
  - `22d2cb42`（S1: guitar was not yet serviced; the user only mentions 'Rhy）
  - `5c40ec5b`（answer_1cb52d0a_1: 'He's actually coming to my city for work）
- **单列**（old/new 共享结论词或 F1 高，区分度弱）：
  - `89941a94`：stale=`Yes (road bike only, before the new purchase)` / new=`Yes (road bike plus newly purchased hybrid bike)`

## 3. 自检结果

参与自检的有效题：**69 / 72**（跳过 3）。
正例 = 用 `stale_value` 当 prediction；负例 = 用 `new_value` 当 prediction。

| 档 | 正例命中 | 负例误命中 | 误命中题 |
|---|---|---|---|
| exact | 69/69 | 0 | — |
| normalized | 69/69 | 0 | — |
| fuzzy@0.7 | 69/69 | 2 | `c4ea545c`, `f685340e` |
| fuzzy@0.8 | 69/69 | 0 | — |
| fuzzy@0.9 | 69/69 | 0 | — |

## 4. 结论与建议

- **默认档 = `normalized`**：正例 69/69，负例误命中 0。
- `exact` 与 `normalized` 的差值主要来自数字词/货币格式（`four` vs `4`、`$400,000` vs `400000`），不是判定分歧。
- `fuzzy` 档的负例误命中来自 old/new 部分重叠（复合答案题），因此 **fuzzy 只用于敏感性分析，不作主判定**。
- 若 0.7/0.8/0.9 三档结论翻转，报告必须写明「判定规则不稳健」，不得改数字。
- `89941a94`（old/new 都是 Yes）与复合答案题的过期检测区分度弱，聚合时单列。

## 5. 复现

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_v1_judge.py
.venv\Scripts\python.exe scripts/audit_ku72_judge.py
```