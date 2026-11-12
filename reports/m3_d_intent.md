> ⚠️ **本产物是旧 prompt 结构（两个 system 消息）的生成结果**；N5 修复后（单 system）重跑可能与表中数字不同，见 §35/D_intent 注。

# D 臂 + 回溯意图识别（V2 154 题）

> 唯一变量：每题先判 current/retrospective，retrospective 时注入「取较早状态」提示。
> 对照：`d_arm_154_run3.json`（D 无意图）。

| 指标 | 值 |
|---|---|
| D + 意图 准确率 | **0.6753** |
| D 对照 准确率 | 0.6623 |
| 配对差 | **+0.0130**（p=0.8145，D_run3_vs_D_intent） |
| 判为 retrospective 的题 | **3 / 154** |

## 解读（诚实）

1. **V2 的 154 题里只有 3 题被判 retrospective（1.9%）**——V2 是环境状态/动态跟踪题，意图基本全是 current，**意图提示几乎没有作用面**。
2. +1.30pp（2 题翻转）在 A/A 噪声底（6.3pp）内，p=0.8145（D_run3_vs_D_run2）→ **不显著，不能称提升**。
3. 这 3 题里 [1, 0, 0]——回溯提示在 V2 上也没有稳定效果（题量太小）。
4. 对照 V1-KU（冲突专项）：意图识别把回溯命中从 **0/9 → 7/9**、当前值 44.4% → 65.1%（`reports/v1_ku_eval.md`）。

**结论**：意图识别不是 V2 主集的提升手段（V2 几乎没有回溯题）；它是 V1 冲突专项的必要能力。产品化保持开启即可，不影响 V2 数字。

## 逐题（意图为 retrospective）

| qid | intent | scores |
|---|---|---|
| `26a038ce` | retrospective | [1] |
| `e9bb843a` | retrospective | [0] |
| `597645be` | retrospective | [0] |

