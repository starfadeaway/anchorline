# `reports/reported_numbers.json` 的符号约定（Z8）

`reported_numbers.json` 里每个 comparison 的字段是自解释的：

```
"diff_a_minus_b": accuracy(a_file) - accuracy(b_file)
```

- `a_file` / `b_file` 指明两侧产物；
- 因此 **json 的正负号可能和 md 正文里的方向表述相反**，这不是错误。

例子：

| 来源 | 写法 | 含义 |
|---|---|---|
| `reported_numbers.json` | `D_run3_vs_D_hybrid.diff_a_minus_b = +0.1039` | `a_file=d_arm_154_run3`（向量）− `b_file=d_arm_154_hybrid` = +0.1039 |
| `reports/d_arm_154_hybrid.md` | 「配对差（hybrid − 向量）= **−0.1039**」 | 同一对比、相反方向表述 |

阅读时**以 `a_file` / `b_file` 为准**，不要只比较数字符号。

## docs/ 排除清单（第 30 轮范围决定，第 31 轮补文档）

`verify_reported_numbers.py` 扫描 `reports/*.md` + `docs/b_c1_c2_single_state_experiment.md`（共 30 个文件）。
以下 docs 文件**显式排除**，因为它们不是当前可重算的评测值：

- `docs/DATASET_LICENSES.md`、`docs/annotation-protocol-ku78.md`：数据集统计/标注协议，百分比不是评测数字；
- `docs/HANDOFF.md`、`docs/legacy_audit_*.md`：历史交接/台账，记录的是已被取代的数字；
- `docs/b_arm_slice_cap_experiment.md`、`docs/b_arm_state_budget.md`、`docs/d_arm_154_v3.md`：旧口径实验记录（保留历史可复现）。

新增受保护文档时，把它加入 `check_markdown` 的 paths；不要靠"在 docs/ 里"就假设有护栏。
