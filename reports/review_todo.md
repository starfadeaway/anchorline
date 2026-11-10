# 评审待办清单（2026-11-11 暂停点）

> 来源：`C:\Users\Liu\Desktop\Anchorline-项目评审报告-2026-11-11.md`（MiniMax 三轮回审）
> 状态：HEAD `48d5c7a`（本批 11 项已修），待明天用户说「继续」后从这里开始。
> 排序 = 建议执行顺序；预估工作量按本地实测速度。

## 已完成（本批，`48d5c7a`）

- [x] P0-6 `FactStore.write(supersedes_id=...)` 统一失效 + 建链；tools 不再预失效（agent 链不再断）
- [x] P0-5 全仓统一 naive 本地时钟（valid_to 不再倒挂 8 小时 / 不再 TypeError）
- [x] P0-7 compose 环境变量 `ANCHORLINE_MYSQL_*` → `MYSQL_*`（与 Settings 一致）
- [x] P0-8 `pyproject.toml` 补 `numpy>=2.0`、`mcp>=2.0`
- [x] P1-8 `data/exports/` 加 `.gitignore` + 移出版本控制
- [x] FE-1 记忆页不再把所有 `user.*` 归「宠物」（改按内容词表）
- [x] FE-2 「事件日期」只写进值文本，`valid_from` 始终是记录时间
- [x] FE-3 审核页按 `entity#簇序号` 作 key/选择键（多簇不串台）
- [x] N2 `conflict_type` enum 对齐协议（时效/语义/偏好反转/无）
- [x] N7 A/A（20 题×10 次）不再覆盖 154 题主跑的 `eval_runs`
- [x] FE-5 SSE + traces 请求带 `X-API-Token`（开鉴权后不再静默 401）

## 待办 · 第 1 优先（评测数字链，明天从这里开始）

- [ ] **P0-1/P0-2 数字一致性 + 确定性 p 值**（预计 60–90min）
  - 写 `scripts/verify_reported_numbers.py`：从 `data/eval/*.json` 的 `per_question` 重算全部 diff/p/n，
    断言 README / `reports/*.md` 里引用的数字与重算值一致；CI 挂进 eval-regression job。
  - 把 `sign_flip_pvalue` 改成**确定性精确符号翻转**（配对差只有 {-1,0,+1}，可闭式/枚举算，不依赖 numpy 版本）。
  - 用新实现重算所有臂的 p 值，更新 `reports/stability_runs.md`、`reports/m3_2x2.md`、`m3_summary.md`、README。
  - 记录：`d_arm_154_run3.json` 的 B 参考臂是 run2（文件时间戳证明 run3 的 B 晚 15 分钟才存在）→ 报告里明确口径或重跑。
- [ ] **P0-3/N5 2×2 归因修正**（40min）
  - `m3_summary.md` §1 改成四格分解：检索粒度（D vs D_neighbor）、L0（C1 vs D_neighbor）、输入模态（B vs C1）；
  - 明确「C1→D 同时变粒度 + 去重，不能归因给压缩」；把「压缩层在 a11y-only +3.2pp / 完整轨迹 +10.4pp（交互效应）」写成主发现。
- [ ] **P0-4 噪声底口径**（20min）
  - 判读阈值改用同臂复跑差（B +3.25pp / D +1.30pp）；撤下或重算 6.3pp；n=1 产物的 `noise_floor` 字段删掉/改名。
- [ ] **N1 M2 常数基线**（30min，只改报告）
  - `conflict_type` / `expected_resolution` gold 零方差（72/72 同值）→ 标「不可评测」或补基线（常数预测 100%）；
  - `reports/m2_quality.md` 每个指标并报众数基线。

## 待办 · 第 2 优先（数据/文档一致性）

- [ ] **N3 分母台账**：README 168→165/167；1a/1b/1c 表述修正；`layer_1c_abstention` 从数据算 + 补 `abstention_excluded_ids`（6 个 id）。
- [ ] **N6 `scoring_mode` 三方写入统一**：`eval_168_judge` / `import_eval_runs` / 迁移 0007 口径统一，避免互相覆盖。
- [ ] **N8 gotchas judge 传参**：`build_gotchas_messages(question, ref, full_response, extracted_answer)` 分开传。
- [ ] **N9 标注链路可复现**：`eval_m2_quality.py` 输出样本量 n；输入清单 + sha256 落盘。
- [ ] **N10 `check_topic_consistency.py` 真的读 `frontend/src/topics.ts`**（或前端导出规则 JSON 双端共用）。
- [ ] **N11 摄入 workflow trace 语义**：session_id 不要塞 traj_id；used_tokens 语义修正；commit 责任明确。
- [ ] **N12 `.env.example` 对齐**：删 `LANCEDB_URI`（无人用）、补 `API_TOKEN/LOG_*/MEMORY_MAX_*/LOREKEEPER_*`；`logging_setup` 改读 Settings。
- [ ] **N13 `run_all.py` 复用 pydantic-settings** 读 .env（去掉手写解析器的引号问题）。
- [ ] **N16/N17 `requirements.lock` 清洗**：导出干净的环境锁（去 httpx2/langchain-protocol 等）；CI 用 lock 安装。

## 待办 · 第 3 优先（P1 链路）

- [ ] **P1-2 索引同步收敛**：`facts_index.sync(fact)` 单一入口（含 PATCH/forget/覆盖/批量清理），`rebuild_facts_index` 进常规流程。
- [ ] **P1-1 物理删除端点治理**：`DELETE /memory/facts/{id}` 与 `DELETE /memory/facts` 改为「导出后可清除 + 二次确认」，README 修正纪律表述（purge 建议下线）。
- [ ] **P1-3 配置脱敏**：`lorekeeper_lance_dir` 默认值清空 + env；CI 密码改 secrets；`/settings` 暴露知识库可用性。
- [ ] **P1-4 CI 回归阈值**：`eval_regression.py` 加 `data/eval/baseline.json` + 容差断言。
- [ ] **P1-5 评测脚本参数化**：`eval_d_arm.py` 的 arm/检索单元/是否 L0 进参数与 config，报告头由 JSON 渲染。
- [ ] **P1-6 检索规模化**：BM25 持久化或倒排；`include_history` 的 `limit(200)` 加 `ORDER BY valid_from DESC`。
- [ ] **P1-7 embedding 批处理**：统一 `embed_in_batches(batch=32)`；索引构建脚本 BATCH 统一。
- [ ] **P1-9 SSE 统一封装**：走 `api.ts` 的 token/超时逻辑（本批只补了 token）。
- [ ] **P1-10 `/memory/search` 死端点**：前端接上或合并 trace 逻辑（召回明细）。
- [ ] **P1-11 `/eval/summary` 维度化**：加 run_id / index_table / n_per_question / retrieval_granularity，前端分组展示。

## 待办 · 第 4 优先（前端体验/防呆）

- [ ] **FE-4 记忆页/会话列表分页**（后端 offset 已支持；导出标注「仅前 N」或全量）。
- [ ] **FE-6/FE-7/FE-8 评测页硬编码数字**：改成从 `/eval/summary` 读，或标注「口径快照」。
- [ ] **FE-10 状态栏「索引」**：用真实索引状态（`/settings` 增加向量索引条目/可用性）。
- [ ] **FE-11 主题色接 antd `colorPrimary`**（读 `--neon` 进 ConfigProvider token）。
- [ ] **FE-12 e2e 清理**：按 entity 的专用删除端点（避免 limit=200 截断）。
- [ ] **FE-18 「测试数据」过滤收紧**：不要按 `/mcp|test|check/` 猜，改显式 entity 前缀。
- [ ] **FE-19 占位符**改成 `user` / `user.猫` / `大模型.名称` 规范。
- [ ] **FE-16 key 用下标**（消息/工具列表）改稳定 key。

## 待办 · P2 精选（收尾时做）

- [ ] P2-1 `WriteResponse` 重复字段删除
- [ ] P2-2 计时中间件测流式响应体（SSE 真实耗时）
- [ ] P2-3 `list_sessions` N+1（COUNT(*) 聚合）
- [ ] P2-6 `InMemorySaver` + 随机 thread_id（内存泄漏）
- [ ] P2-9 `_verify_and_retry_answer` 数字匹配（子串假阴性/中文数字不互通）
- [ ] P2-10 `ChatClient.stream` 补重试
- [ ] P2-11 `redacted()` 补 `api_token`
- [ ] P2-12 `mysql_dsn` 密码 URL 编码
- [ ] P2-20 `LICENSE` 文件（ADR-000 拍板）
- [ ] P2-22 `conflict_type` 工具 schema 与协议（已在 N2 修 enum，需重跑 M2 验证）
- [ ] N18 删除作废的 `b_arm_154.json` / `d_arm_154.json`（或移入 `_deprecated/`）
- [ ] N19 metrics `error_rate` 纳入 4xx
- [ ] N20/N21 metrics key 基数、QPS 口径、进程内 deque 说明
- [ ] N22 `pilot.py` 抽样 RNG 与重试抖动隔离
- [ ] N23/N24 merge_annotations 的 null 语义与 assert（`python -O` 失效）

## 明天开始的第一条命令

```powershell
cd C:\Users\Liu\Desktop\ai实验\DeepSeek\Anchorline
git pull
# 从 P0-1/P0-2 开始：先写 verify_reported_numbers.py + 确定性 sign-flip，再重算全部 p 值
```
