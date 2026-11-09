# 跨模型交叉标注报告（MiniMax vs 人类）

> 用途：检验**标注协议是否可复现**（另一个模型按同一协议能否得出同样结论）。
> ⚠️ 这是**机器交叉检查，不是第二人类标注者**；报告措辞不得写「双人标注」。
> 它与「人类自重复（间隔 ≥7 天 / 盲标）」是两件事，不能互相替代。

## 1. 配置

- 模型：`MiniMax-M3`（`https://api.minimax.chat/v1`，temperature 0，max_tokens 8192）
- 样本：16 题 = 5 道争议题（`89941a94`、`c4ea545c`、`f685340e`、`031748ae`、`22d2cb42`）+ 11 道随机（seed=7）
- 盲标：只给题面、官方 answer、两个 gold session 全文，**不给人类标注**
- 提示词内置 v3.1 规则（双槽位→current、复合答案→具体值、null 旧值）

## 2. 一致率（16 / 16 全部可解析）

| 指标 | 数值 |
|---|---|
| `query_form` 一致 | **16/16** |
| `stale_value` 值等价 | **15/16** |
| `new_value` 值等价 | **15/16** |
| 三项全一致 | **15/16** |

> 值等价口径：归一化后相等，或内容词集合有包含关系（如 `4 engineers` ⊃ `4`、`30 dozen` ⊃ `30`），或 token F1 ≥ 0.8。

## 3. 分歧题

### `89941a94`

- 模型：qf=`retrospective`, stale=`three bikes: road bike, mountain bike, and commuter bike`, new=`four bikes: road bike, mountain bike, commuter bike, and hybrid bike`
- 人类：qf=`retrospective`, stale=`Yes (road bike only, before the new purchase)`, new=`Yes (road bike plus newly purchased hybrid bike)`
- 模型 note：The road bike existed before the purchase, and the later session adds a hybrid bike, although the question calls it a gravel bike.

## 4. 结论

1. **方向（`query_form`）16/16 一致**：双槽位题在提示词写入 v3.1 规则后，模型与人类判断一致。
2. **值粒度差异大于方向差异**：剩余分歧集中在「模型给更具体值（`4 engineers` / `30 dozen` / `in my bedroom`）」 vs 「人类给短值（`4` / `30` / `in the bedroom`）」，方向没有错。
3. **模型不能替代人类自重复**：它测的是协议可复现性；且两个模型可能共享偏差。人类自重复（间隔 ≥7 天或盲标）仍需单独做。
4. 这份交叉检查已满足协议 §6 三件套中的「跨模型交叉」一项；报告分列两项一致率，不合并、不写「双人标注」。

## 5. 复现

```powershell
.venv\Scripts\python.exe scripts/cross_model_annotate.py   # 调 MiniMax 16 题
.venv\Scripts\python.exe scripts/cross_model_compare.py    # 值等价重算
```