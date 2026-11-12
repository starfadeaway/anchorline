# Anchorline

在**固定 token 预算**下，把多轮对话 / Agent 轨迹压成可回答、可追溯的记忆，并用公开基准回答：**在同样预算下，记忆层相对无记忆、官方 RAG、全量历史，是否真的更好。**

不是「再做一个 RAG」，也不是「又一个聊天机器人」。**可复现、可防守的记忆工程**，不是研究前沿。

## 两个基准（能力面不重叠，互不合并）

| 基准 | 角色 | 分母 |
|---|---|---|
| **LongMemEval-V2 web 子集** | 主评测（环境状态 / 动态跟踪 / 流程 / 陷阱 / 前提） | **名义 168**（154 确定性 + 14 judge；judge 解析失败的题从两臂剔除 → run2 **165** / run3 **167**） |
| **LongMemEval-S knowledge-update** | 冲突专项（过期事实 / 冲突裁决 / 回溯意图） | **72 可判**（1a 63 / 1b 9）；1c 的 6 道是 78 题中**被剔除的拒答变体**，不在 72 内（见 `reports/ku72_build.md`） |

> 168 与 72 都是「该阶段的冻结口径」，不是不可变的最终分母；改口径必须写进文档。

## 与 LoreKeeper 的定位边界

- **Anchorline = 会话/轨迹的记忆层**：事实级（entity / attribute / value），管冲突、回溯、预算。
- **LoreKeeper = 游戏 wiki 的知识库**：chunk / 页面级检索问答。
- 两者的桥接只复用 **检索组件**（BM25 / 向量 / RRF / rerank）在 LoreKeeper 数据集上做对照实验（见 `reports/lorekeeper_bridge.md`），**不是把两个项目合并**。
- 聊天里的 `memory_search` 只查 Anchorline 的 facts；对 LoreKeeper 知识库的检索是 `kb_search`（**已接入聊天工具与 MCP**；`LOREKEEPER_ENABLED=false` 可关闭）。

## 技术栈（已锁定）

- Python **3.13** 单环境；FastAPI + Pydantic + SQLAlchemy 2 + Alembic
- **MySQL 8**（事实 / 会话 / trace / eval_runs / 审核裁决）+ **LanceDB**（向量）+ BM25；向量不进 MySQL
- **LangGraph StateGraph**（不是 LangChain 全家桶；不写 `AgentExecutor` 壳）
- 原生 **function calling** + MCP（`memory_search` / `memory_write` / `memory_forget`）
- React 19 + TypeScript + Vite + Ant Design 5 + SSE

## 目录

```text
src/anchorline/            # 记忆层（L0/L1/L2/L3）、检索（hybrid/facts_index）、图（chat/workflows）、API、MCP
frontend/                  # React 前端（聊天/记忆/评测/审核/报告/监控/会话管理/设置）
migrations/                # Alembic（0001 初始 → 0014：session.topic / trace.recalls / review_decisions / 表注释 / scoring_mode / 技能开关与绑定 / 自定义技能等）
scripts/                   # 评测、索引构建、demo、桥接实验、数据清理
reports/                   # 29 份评测/审计/整改报告（项目最核心的证据资产）
tests/                     # pytest（152 项）
docs/                      # 协议、许可、ADR、评测结果、桥接报告
dataset/                   # 数据与核验产物（大文件不入库）
```

## 界面截图

> 截图中的会话、记忆与 trace 均来自测试数据（非真实用户数据，已获授权公开）。
> `scripts/make_screenshots.py` 直接对运行中的实例截图，**不做脱敏**——只有在实例里全是测试数据时才可提交截图。

### 聊天（用户右 / 模型左、主题分组、技能提示）

![聊天页](docs/screenshots/01-chat.png)

### 记忆（容量提示、当前/失效、分组）

![记忆页](docs/screenshots/02-memory.png)

### 评测（臂对比 + A/A 噪声底 + LoreKeeper 桥接）

![评测页](docs/screenshots/03-eval.png)

### 审核（冲突裁决金标）

![审核页](docs/screenshots/04-review.png)

### 报告中心（记忆/会话/评测 Markdown 导出）

![报告页](docs/screenshots/05-reports.png)

### 监控（延迟 / 错误率 / trace）

![监控页](docs/screenshots/06-monitor.png)

### 设置（主题色 / 日夜模式）

![设置页](docs/screenshots/07-settings.png)

## 当前状态

- **M0a/M0b 完成**：G1 15/15 自洽（k=0）；V1-KU 72 题标注完成（63/9/6）
- **M1 完成**：L0/L1/L2/L3、事实存储（supersedes + 容量归档）、LangGraph 聊天（真实 tool calling）、MCP 三工具、FastAPI、Alembic
- **M2 前端完成**：聊天（会话主题分组/召回明细）、记忆（主题分组/环形图/删除）、评测（臂对比/Trace/LoreKeeper 桥接）、审核（冲突裁决金标）、报告、监控、会话管理、设置（主题色/日夜）
- **M3 评测（同 reader/embedding/判分/4k 预算）**：B 53.9% / C2 57.1% / D 64.9%（154 题，**run2 口径**；B/D 同批、C2 单批；D vs B **p=0.0115**，精确符号翻转）；168 题 run2 B 53.3% vs D 63.6%（p=0.0186）、run3 B 56.3% vs D 64.7%（**p=0.0541 边缘**）；重复运行单题翻转 ~12%，154 上 D>B 两次都显著 → `reports/stability_runs.md`；报告数字由 `scripts/verify_reported_numbers.py` 校验
- **M3 2×2 因子**：B（a11y×官方切片）/ C2（a11y×L0+L3）/ C1（完整轨迹×官方切片）/ D（完整轨迹×L0+L3），配对检验 → `reports/m3_2x2.md`
- **LoreKeeper 桥接实验**：48 题页面级召回——纯向量 R@1 0.8542；chunk 级 RRF 单用有害（0.7917）、**RRF+rerank 0.8958（+4.17pp）**；**页面级重排 0.9167**；chunk 级自动 gold 与换向量口径见 `reports/lorekeeper_bridge.md`

## 常见问题

- **前端能打开但接口全 500？** 先确认 MySQL 在跑（`run_all.py` 会预检；失败会直接退出并给提示）。
- **`kb_search` 总是空？** 需要 `LOREKEEPER_ENABLED=true` 且 `LOREKEEPER_LANCE_DIR` 指向 LoreKeeper 的 LanceDB 目录；未配置时工具返回空是预期行为。
- **开了 `API_TOKEN` 后页面 401？** 在「设置」页填入同一个 token（只存 localStorage）。
- **报告数字和 JSON 产物对不上？** 跑 `python scripts/verify_reported_numbers.py`（CI 也用它）。
- **记忆页首次进入慢？** 分组默认只展开前 2 组（懒渲染）；展开更多组会按需渲染。

## API Token 鉴权（可选）

> 定位：**后端的门禁密码**（共享密钥），不是用户账号系统。默认关闭；本地自用不用管。

**它保护什么**：设置 `API_TOKEN` 后，除 `/health`、`/docs`、`/openapi.json`、`/redoc` 外，
所有 API 都要求请求头 `X-API-Token: <token>`（也接受 `Authorization: Bearer <token>`），否则 401。
前端在「设置」页填同一个 token 后，会把请求自动带上该头（只存浏览器 localStorage）。

### 启用步骤

```powershell
# 1) 生成一串随机密码（这就是"项目密码"）
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(24))"

# 2) 写进项目根 .env（不要提交）
#    API_TOKEN=<上一步的输出>

# 3) 无需重启：中间件每次请求都会重新读 .env，改完立即生效（如果你用 run_all 起的服务，也建议重启一次确认）
.venv\Scripts\python.exe run_all.py
```

然后打开「设置」页 → API Token → 填入同一串 → 保存 → 刷新。

### 验证

```powershell
curl.exe -i http://127.0.0.1:8000/skills
# → 401（缺少 token）
curl.exe -H "X-API-Token: <token>" http://127.0.0.1:8000/skills
# → 200
curl.exe http://127.0.0.1:8000/health
# → 200（health 永远免鉴权，方便探活）
```

### 典型场景：局域网给同事演示

1. 设好 `API_TOKEN` 并重启；
2. 前端对外监听：`cd frontend; npm run dev -- --host 0.0.0.0`（并在防火墙放行 5173）；
3. 同事打开 `http://<你的局域网IP>:5173`：页面能打开，但数据加载 401；
4. 把 token 发给同事 → 他在「设置」页填入 → 刷新即正常；
5. 演完把 `.env` 里的 `API_TOKEN` 换成新串（或删掉）→ 重启 → 旧 token 立即失效。

### 边界与注意

- 一个 token 通行所有请求：没有账号、多用户或细粒度权限；
- token 明文存储（`.env` + 浏览器 localStorage），**`.env` 已在 `.gitignore`，不要提交**；
- 暴露公网时请放在 **HTTPS 反向代理**后面，否则 token 明文过网；
- 换浏览器/清缓存后需重新在设置页填写；
- 不是加密；**限流是进程内的**（聊天/生成约 30 次/分钟；多进程/多副本部署时限额按副本数放大，重启清零）——它只是"能不能调用 API"的开关与轻量护栏。

## 快速开始

```powershell
# 0) 依赖（Python 3.13）
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 1) 配置（模板，不含真实 key）
Copy-Item .env.example .env   # 填 MySQL 与 provider key

# 2) 数据库（MySQL 8 运行中）
.venv\Scripts\python.exe -m alembic upgrade head

# 3) 一键启动前后端（仿 lorekeeper run_all.py；Ctrl+C 同时停止）
.venv\Scripts\python.exe run_all.py
#    只起后端：run_all.py --only server
#    只起前端：run_all.py --only client

# 或分别启动：
# $env:PYTHONPATH='src'; .venv\Scripts\python.exe -m uvicorn anchorline.api.main:app --host 127.0.0.1 --port 8000
# cd frontend; npm run dev
```

## Docker 部署

```powershell
# 1) 准备 .env（从 .env.example 复制）
#    - MYSQL_PASSWORD 必填 = compose 内 MySQL 的 root 口令
#    - API_TOKEN 必填 = 前后端共享的访问口令（见下方「反代也是通路」）
Copy-Item .env.example .env

# 2) 先构建向量索引（需要 dataset/ 与 SILICONFLOW_API_KEY；否则检索退化为 BM25）
.venv\Scripts\python.exe scripts\build_baseline_index.py --radius 0

# 3) 启动 MySQL + API + 前端
docker compose up -d --build

# 4) 访问
#   前端  http://127.0.0.1:8080（VM 部署用 VM 的 IP:8080）
#   API   http://127.0.0.1:8000/health（只绑回环；外部经前端 /api 代理）
#   首次打开前端：到「设置」页填入与 .env 相同的 API_TOKEN，否则请求会 401
```

部署安全要点：

- **MySQL 不暴露 3306**（只在 compose 内网被 api 访问）；root 口令来自 `.env` 的 `MYSQL_PASSWORD`（单一来源，必填，缺失时 compose 直接报错）。
- **鉴权**：设置 `API_TOKEN` 后，请求需带 `X-API-Token: <token>` 或 `Authorization: Bearer <token>`（scheme 大小写不敏感）。改 `.env` 后需重启 API 才生效（中间件缓存 Settings，换取每请求少读一次盘）。
- **API 只绑 `127.0.0.1:8000`**；但**前端 `8080` 的 `/api/*` 反代本身就是通路**（nginx 不做鉴权）——局域网访问 `http://<VM>:8080/api/chat/stream` 同样能消耗 provider 额度。因此**必须设置 `API_TOKEN`**（前端设置页填同一个 token），两条通路一起关；只绑回环不等于安全。
- **向量索引**：`./data/lancedb` 已挂载进 api 容器；克隆后没有索引时检索会退化成 BM25，需要先跑索引构建（见「实验与复现」/`scripts/build_baseline_index.py`）。
- `dataset/` 不入库——**评测/索引脚本需要先准备 `dataset/`**，否则会明确报错退出；容器默认不含评测数据，做评测时取消 compose 里 dataset 挂载的注释。
- **历史重写过**：VM/其他机器上的旧 clone 需要重新拉取（`git fetch` 旧引用会失败）。

## B 臂口径（重要）

- **B ≈ 官方基线的 a11y 通道子集**：官方 baseline 还有 event/note 通道、controller 生成的改写查询与动作序列/截图；本项目只复刻 a11y 通道（见 dataset/v2/official_repo/）。
- **当前口径（2026-11-12 起）：B/C1/C2 的索引单元是单 state**（每条 entry = center state 的 AXTree；B median 15,998 字符、cap 16000），与 D（median 702）粒度一致。**旧 3-state 口径**（median 49,341 / 39,998 字符）在 4k 预算下保头截断会丢掉 center——B 57.14→60.39、C1 53.90→57.14、C2 净值不变；两口径对照见 `docs/b_c1_c2_single_state_experiment.md`。
- **单 state 数字需重建索引才能复现**：`data/lancedb/` 不入库，克隆后跑 `build_baseline_index.py --radius 0` / `build_c1_arm_index.py --radius 0`（各 1737 条 embedding），且 re-embedding 不保证逐位相同。
- **按 `预算 ÷ top_k ≈ 2666` 封顶经实测不采用**：重建索引后 B 从 **57.14% 降到 43.51%**（配对差 −13.64pp，精确符号翻转 **p=0.0011**，39/154 题变化）。结论与证据见 `docs/b_arm_slice_cap_experiment.md`；默认封顶改为**预算字符数（16000）**，可用 `ANCHORLINE_INDEX_SLICE_CAP` 覆盖。
- 因此 **B 的绝对准确率不代表官方基线全貌**，只用于本项目内部同预算对照（B vs C1/C2/D）。
- **历史产物（b/c2/d/hybrid/intent）是旧代码路径生成的**：截断标记、system 合并、Similarity 标签是后续修复；重跑会与 `reports/` 中的旧数字不同（未重跑，因为需要 provider key 与索引重建）。

## 核心能力

| 能力 | 说明 | 命令/入口 |
|---|---|---|
| 记忆层 | L0 跨 state 行去重 → L1 观测摘要 → L2 事实（supersedes）→ L3 预算组装 | `src/anchorline/memory/` |
| **技能（可开关）** | 独立「技能」页：内置 4 个技能（跑步教练 / 饮食规划 / 知识库问答 / 记忆整理）+ 用户自定义；支持开关、模板、按描述自动生成、绑定记忆实体、关键词自动激活。聊天时把启用技能指令拼进 system prompt——指令影响**回答方式与写入建议**（memory_hygiene 会引导 supersedes_id，倒挂/链指向防护见 memory/store.py）；**评测走独立 prompt 组装链路，不受技能开关影响**（技能只占产品侧 system prompt 预算） |
| **混合检索** | jieba + BM25Plus + 向量（Qwen3-Embedding/LanceDB）+ RRF + BGE rerank；失败自动回退。**注意：在 V2 轨迹长文本上实测 −10.4pp（p=0.0195，相对纯向量，见 `reports/d_arm_154_hybrid.md`）——主评测因此保持纯向量；产品侧目前只用于短事实文本（**该场景尚未做对照实验，不能视为已验证**） | `memory_search` 工具 / `POST /memory/search` |
| **知识库问答（可选）** | `kb_search` 工具查 LoreKeeper 三库 wiki（sr/ys/zzz，页面级重排），与事实记忆分工；关掉 `LOREKEEPER_ENABLED` 即禁用 | 聊天 / MCP |
| **容量保护** | 每实体当前值上限（默认 200，`MEMORY_MAX_CURRENT_PER_ENTITY`），超限自动归档最旧/低置信度（标记失效） | `GET /memory/capacity` |
| **召回可解释** | 每条召回的 BM25/向量/RRF/rerank 分数写入 trace，前端 Trace 面板展示 | `trace.recalls` |
| **冲突裁决** | 审核页：选一条保留、其余失效、记录原因 → `review_decisions` 金标 | `POST /review/decisions` |
| 可追溯 | 事实不物理删除；历史、失效时间、裁决记录可查 | `GET /memory/facts/{id}/history` |
| 会话主题 | 模型生成 topic（如“跑步/游泳/乒乓球”），前端按主题分组 | `sessions.topic` |
| 报告导出 | 记忆 / 会话 / 评测 Markdown 导出 | 前端「报告」页 |
| 审核裁决金标 | 审核页裁决（保留 + 失效 + 原因）写入 `review_decisions`，评测页「审核裁决」Tab 展示 | `POST /review/decisions` |

## 实验与复现

```powershell
# 单元测试
.venv\Scripts\python.exe -m pytest -q

# 一键 demo：写入 → 更新（旧值自动失效）→ 混合检索 → 容量 → 清理
.venv\Scripts\python.exe scripts\demo.py

# 全量重建事实向量索引（写入时已同步，脚本用于初始化/修复）
.venv\Scripts\python.exe scripts\rebuild_facts_index.py

# V2 评测（B / C2 / D / 168）
.venv\Scripts\python.exe scripts\aa_pilot.py --limit 154 --n 1 --out data\eval\b_arm_154_run2.json
.venv\Scripts\python.exe scripts\eval_c2_arm.py --limit 154
.venv\Scripts\python.exe scripts\eval_d_arm.py --limit 154 --n 1 --table v2_web_states_d --b-ref data\eval\b_arm_154_run2.json --out data\eval\d_arm_154_run2.json
.venv\Scripts\python.exe scripts\eval_168_judge.py

# LoreKeeper 数据集桥接（页面级 Recall/MRR）
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --k 5
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --mode page --k 5

# chunk 级（自动 gold）与换向量口径
.venv\Scripts\python.exe scripts\lorekeeper_chunk_gold.py --by bm25
.venv\Scripts\python.exe scripts\lorekeeper_chunk_eval.py --k 5 --gold data\eval\lorekeeper_chunk_gold_bm25.json

# M2 记忆质量（V1 72 题）与 L2 事实抽取
.venv\Scripts\python.exe scripts\eval_m2_quality.py
.venv\Scripts\python.exe scripts\eval_l2_extraction.py
```

## 工程与运维

| 项 | 用法 |
|---|---|
| 一键启动 | `.venv\Scripts\python.exe run_all.py`（`--only server\|client`、`--port`） |
| Lint | `.venv\Scripts\python.exe -m ruff check src tests scripts run_all.py examples` |
| 测试 | `.venv\Scripts\python.exe -m pytest -q`；CI 里带 `--cov=src/anchorline` |
| e2e | `cd frontend; npm run e2e`（本地真实模型用例：`$env:REAL_E2E='1'; npm run e2e`） |
| 备份/恢复 | `scripts\backup_db.ps1` / `scripts\restore_db.ps1 -File <sql>` |
| MCP 客户端示例 | `.venv\Scripts\python.exe examples\mcp_client.py` |
| 日志 | 默认文本；`LOG_FORMAT=json` 输出结构化 JSON，`LOG_LEVEL=DEBUG` 调级别 |
| 流式 | 默认伪流式（答案生成后逐块）；`STREAM_MODE=real` 时真 token 流（多一次模型调用） |
| 依赖锁 | `requirements.lock`（`pip freeze`） |

## 数据与许可边界

- V2 = Apache-2.0（轨迹原文可入库，保留 LICENSE + NOTICE）；**不下载 5.92 GB 轨迹截图包**
- V1-S 的 MIT 只覆盖 benchmark 自身；**session 原文不入库**
- PerLTQA / engram-eval / LoCoMo 等非商用数据不入库
- **API Key 只经 `.env` 读取**，不入库、不进日志、不进对话；`.env.example` 只有占位符

## 术语表（评测口径）

- **trajectory（轨迹）**：一次完整的 web 任务会话，按 step 排列多个 state。
- **state**：轨迹里的一个时间点快照，含 `URL / Action / AXTree`（C1/D 的模板还含 thought）。记忆评测的「旧值 / 当前值」分布在不同 state 里——检索命中哪个 state 决定能否拿到答案。
- **AXTree（可访问性树）**：浏览器导出的页面语义树（角色、名字、可见/可点击等，如 `[227] link 'My Account', clickable, visible`）。Web Agent（WebArena baseline）读它而不是截图/HTML。
- **a11y-only**：只用可访问性树作页面输入，不含截图/DOM。B/C2 属于该模态；C1/D 是「完整轨迹」（模板额外含 thought）。
- **entry（检索单元）**：向量索引里的一行 = 一段文本 + 它的 embedding；检索返回 top-k。
- **radius / 3-state / 单 state**：radius=1 时 entry 是 `center−1, center, center+1` 三个 state 的拼接；radius=0 只含 center。3-state 在 4k 预算下会被保头截断，**丢掉 center**——本项目 2026-11-12 起 B/C1/C2 改为单 state。
- **top-k / 预算**：检索取前 6 条；每题上下文预算 4k tokens（按 chars/4 近似）。

## 评测口径修正（2026-11-12）

B/C1/C2 的索引从 **3-state 邻域**改为**单 state**：旧口径下 4k 预算的保头截断会切掉 center，注入内容与检索命中的 state 错位。

| 臂 | 旧（3-state） | 单 state |
|---|---|---|
| B | 57.14% | **60.39%** |
| C1 | 53.90% | **57.14%** |
| C2 | 57.14% | 57.14% |
| D | 66.23% | 66.23% |

**结论变化**：`B → D` 的显著性消失（+5.84pp，**p=0.2327**；旧 0.0385）——旧「D 是唯一显著优于 B 的臂」**部分建立在 B 索引缺陷上，且本身很脆弱**（p=0.0385 在少 1 题时即变 0.0807）；修正后差距 5.84pp、p=0.2327 —— **准确的说法是我们此前高估了结论强度，不是旧数字错了**。`C1 → D_neighbor` 也不再显著（+7.14pp，p=0.1263）。C1→D 仍显著（+9.09pp，p=0.0201）。

旧口径产物保留在 `data/eval/*_run3.json`、`c1_arm_154.json`、`c2_arm_154.json`（历史可复现）；单 state 产物为 `*_single_state.json`。完整记录见 `docs/b_c1_c2_single_state_experiment.md`。
