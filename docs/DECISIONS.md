# ADR 索引 / DECISIONS

> 只记录**已锁定**或**待拍板**的架构决策；执行方案以 v0.8 为准（本地 `简历/多轮记忆与上下文预算-方案-v0.8.md`）。
> 本文件只列条目与依据，不复制方案全文。

| 编号 | 决策 | 状态 | 依据 |
|---|---|---|---|
| ADR-000 | **代码许可**：MIT / Apache-2.0 二选一 | ⬜ **待拍板** | v0.8 要求写 ADR；未定前不创建 `LICENSE`，避免默认许可 |
| ADR-001 | 独立仓库 `anchorline`，**不放进 lorekeeper** | ✅ 已定 | 启动提示词已锁定 |
| ADR-002 | **许可与技术边界**：V2 Apache-2.0 轨迹可入库；V1-S session 原文不入库；非商用数据（PerLTQA / engram-eval / LoCoMo）不入库；不下载 5.92 GB 截图包；数据与代码分许可 | ✅ 已定 | v0.8 §7 |
| ADR-003 | **评测设计**：V2-web 6 臂（A / B / C1 / C2 / D / E，2×2 因子设计）、V1-KU 3 臂、A/A 只在 pilot 20×10、M3 矩阵 2,339 次 | 🔲 可起草，**待落 ADR** | v0.8 §6 |
| ADR-004 | **运行时与依赖**：Python 3.13 单环境、MySQL 8 + LanceDB + BM25、LangGraph StateGraph、单 API 副本 | 🔲 可起草，**待落 ADR** | v0.8 §4 / §5 |
| ADR-005 | **V2 臂只跑 insert + query**；写入侧（merge / supersede / conflict / consolidation）只在 V1-KU | ✅ 已定 | v0.8 §4 / §5 |
| ADR-006 | **指标名固定**：V1 用「与标注协议的一致率」，不用「裁决准确率」 | ✅ 已定 | v0.8 §6.2.2 |
| ADR-007 | **不进官方 leaderboard**，只报同 reader / judge / embedding / 预算下的相对结果 | ✅ 已定 | v0.8 §10 |

## 待办

- ADR-003 / ADR-004 起草（不改 v0.8 结构）
- ADR-000 等用户拍板后创建 `LICENSE` 并补 `NOTICE`
