# ADR 索引 / DECISIONS

> 只记录**已锁定**或**待拍板**的架构决策；执行方案以 v0.8 为准（本地 `简历/多轮记忆与上下文预算-方案-v0.8.md`）。
> 本文件只列条目与依据，不复制方案全文。

| 编号 | 决策 | 状态 | 依据 |
|---|---|---|---|
| ADR-000 | **代码许可**：**MIT**（2026-11-11 拍板，仓库根 `LICENSE`） | ✅ 已定 | v0.8 要求写 ADR；MIT 允许展示与复用，数据许可仍按 ADR-002 分开 |
| ADR-001 | 独立仓库 `anchorline`，**不放进 lorekeeper** | ✅ 已定 | 启动提示词已锁定 |
| ADR-002 | **许可与技术边界**：V2 Apache-2.0 轨迹可入库；V1-S session 原文不入库；非商用数据（PerLTQA / engram-eval / LoCoMo）不入库；不下载 5.92 GB 截图包；数据与代码分许可 | ✅ 已定 | v0.8 §7 |
| ADR-003 | **评测设计**：V2-web 以 B / C1 / C2 / D 的 2×2 因子为主（A/E 仅 pilot）；**单变量对比**必须只改一个因子（C1→D_neighbor 隔离压缩、D→D_neighbor 隔离粒度；C1→D 是双变量，不能单独归因）；V1-KU 3 臂；p 值用**确定性精确符号翻转**；A/A 只在 pilot 20×10（不代表 D 臂）；M3 矩阵 2,339 次 | ✅ 已落（2026-11-11） | v0.8 §6 + 第四轮评审 §17.3 |
| ADR-004 | **运行时与依赖**：Python 3.13 单环境；MySQL 8（事实/会话/trace/eval_runs/裁决）+ LanceDB（向量）+ BM25（每次查询重建，规模化是已知限制）；LangGraph StateGraph；FastAPI 单副本（指标为进程内 deque）；MCP 2.x（`mcp` 已进 pyproject） | ✅ 已落（2026-11-11） | v0.8 §4 / §5 |
| ADR-005 | **V2 臂只跑 insert + query**；写入侧（merge / supersede / conflict / consolidation）只在 V1-KU | ✅ 已定 | v0.8 §4 / §5 |
| ADR-006 | **指标名固定**：V1 用「与标注协议的一致率」，不用「裁决准确率」 | ✅ 已定 | v0.8 §6.2.2 |
| ADR-007 | **不进官方 leaderboard**，只报同 reader / judge / embedding / 预算下的相对结果 | ✅ 已定 | v0.8 §10 |
| ADR-008 | **pilot 模型配置**：reader + judge = `deepseek-flash`（DeepSeek，1M ctx，reasoning 模型需给足 max_tokens）；embedding = `Qwen/Qwen3-Embedding-8B`（SiliconFlow，4096 维）；rerank = `BAAI/bge-reranker-v2-m3`。评测模式冻结，换模型只用于聊天模式 | ⚠️ **pilot 配置，待拍板** | v0.8 §2.2 provider 分工；与官方默认（Qwen3.5-9B / Qwen3-Embedding-8B / gpt-5.2）不同，报告只报同配置相对结果 |

## 待办

- ADR-003 / ADR-004 ✅ 已落（2026-11-11）
- ADR-000 ✅ MIT（`LICENSE` 已创建，可补 `NOTICE`）


## 口径备注

- **token 估算口径**：仓库里 chars/4 只是预算近似（不是模型 tokenizer）；	otal_tokens 等字段为字符数/4 的估计值。
  报告里的「4k 预算」是名义值，三臂同口径比较成立，绝对值需用真实 tokenizer 复核（已知局限）。
- **p 值口径**：scripts/eval_stats.py 的精确符号翻转（与 numpy 版本/seed 无关）；报告数字由 scripts/verify_reported_numbers.py 校验。
