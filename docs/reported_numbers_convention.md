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
