# MiniMax agent 交叉标注 vs 人类标注（独立比对）

> 数据：`data/annotations/ku72.jsonl`（人类，gold 起点）与
> `dataset/v1/minimax-package/annotations-minimax.jsonl`（MiniMax Code agent，72 行盲标）。
> 比对口径：`query_form` 严格相等；`stale/new` 用 `value_equivalent`（归一化 + 内容词包含 + F1≥0.8）。

## 1. 结果

| 指标 | 一致 |
|---|---|
| `query_form` | **72/72** |
| `stale_value` | **68/72** |
| `new_value` | **71/72** |
| `conflict_type` | **72/72** |
| `expected_resolution` | **71/72** |
| qf+stale+new 全一致 | **68/72** |

## 2. 分歧题（需人工仲裁）

### `d7c942c3`

- MiniMax：qf=`current`, stale=`mom still uses her old paper list (not the same method)`, new=`mom now uses the same grocery list app as me`, resolution=`覆盖`
- 人类：qf=`current`, stale=`No.`, new=`Yes.`, resolution=`覆盖`
- MiniMax note：A=妈妈仍用纸质清单, B=妈妈改用同一 grocery list app; 问现在, 官方=Yes 与B一致(new_value填具体方式而非Yes)
- **仲裁**：表述差异（语义等价） → 保留人类 `Yes./No.`；MiniMax 的具体描述可入 note，不改 gold

### `b01defab`

- MiniMax：qf=`current`, stale=`None`, new=`Yes`, resolution=`覆盖`
- 人类：qf=`current`, stale=`No`, new=`Yes`, resolution=`覆盖`
- MiniMax note：A=读到一半搁置、尚未读完(旧状态未发生→stale_value=null), B=已读完(Yes); 问是否读完
- **仲裁**：规则分歧：null vs No → 保留人类 `No`。协议 v3.2 补充：布尔事实的旧状态为 No 时填 `No`；`null` 只用于「该事实此前从未存在」（如从未送修/从未见面）

### `5831f84d`

- MiniMax：qf=`current`, stale=`12`, new=`15`, resolution=`覆盖`
- 人类：qf=`current`, stale=`10`, new=`15`, resolution=`覆盖`
- MiniMax note：A=10→12(用户后续纠正为刚看完第12个), B=15(用户说已看15个); 问现在
- **仲裁**：口径分歧：12 vs 10 → 保留人类 `10`。题目限定 `in the past few weeks`；`12` 是同 session 的累计口径，不是问题时间窗

### `89941a94`

- MiniMax：qf=`retrospective`, stale=`Yes - a road bike (three bikes before the purchase: road, mountain, commuter)`, new=`Yes - a road bike (plus the newly purchased hybrid bike; four bikes in total)`, resolution=`覆盖`
- 人类：qf=`retrospective`, stale=`Yes (road bike only, before the new purchase)`, new=`Yes (road bike plus newly purchased hybrid bike)`, resolution=`覆盖`
- MiniMax note：A=road+mountain+commuter共3辆(user), B=加新购hybrid共4辆(user); 题面问购买前故官方=Yes(road bike)对应A的旧状态,当前状态见B; 题面称gravel bike而材料称hybrid bike
- **仲裁**：表述差异（语义等价） → 保留人类值；该题 old/new 均含 `Yes`，已标 ambiguous，聚合单列

## 3. 人工仲裁结论

| qid | 分歧性质 | 裁决 |
|---|---|---|
| `d7c942c3` | 表述差异（语义等价） | 保留人类 `Yes./No.`；MiniMax 的具体描述可入 note，不改 gold |
| `b01defab` | 规则分歧：null vs No | 保留人类 `No`。协议 v3.2 补充：布尔事实的旧状态为 No 时填 `No`；`null` 只用于「该事实此前从未存在」（如从未送修/从未见面） |
| `5831f84d` | 口径分歧：12 vs 10 | 保留人类 `10`。题目限定 `in the past few weeks`；`12` 是同 session 的累计口径，不是问题时间窗 |
| `89941a94` | 表述差异（语义等价） | 保留人类值；该题 old/new 均含 `Yes`，已标 ambiguous，聚合单列 |

**真分歧 2 题**（`b01defab`、`5831f84d`）均保留人类值；另 2 题（`d7c942c3`、`89941a94`）为表述差异，语义等价。

## 4. 结论与口径

1. 分层完全一致：MiniMax 与人类都是 **current 63 / retrospective 9**。
2. 值层面：`stale` 68/72、`new` 71/72；4 道分歧经人工仲裁后，gold 保持人类标注。
3. 报告口径：**「gold 由人类标注 + MiniMax agent 交叉标注 + 人类仲裁分歧题；无第二人类标注者」**。
4. 不写「双人标注」；不写「模型自行标注即 gold」。

## 5. 复现

```powershell
.venv\Scripts\python.exe scripts/make_minimax_package.py   # 生成标注包
.venv\Scripts\python.exe scripts/compare_minimax.py        # 独立比对 + 仲裁
```