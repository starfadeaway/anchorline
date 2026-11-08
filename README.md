# Anchorline

在**固定 token 预算**下，把多轮对话 / Agent 轨迹压成可回答、可追溯的记忆，并用公开基准回答：**在同样预算下，记忆层相对无记忆、官方 RAG、全量历史，是否真的更好。**

不是「再做一个 RAG」，也不是「又一个聊天机器人」。**可复现、可防守的记忆工程**，不是研究前沿。

## 两个基准（能力面不重叠，互不合并）

| 基准 | 角色 | 分母 |
|---|---|---|
| **LongMemEval-V2 web 子集** | 主评测（环境状态 / 动态跟踪 / 流程 / 陷阱 / 前提） | **168 − k**，k ≤ 15；168 目前 provisional |
| **LongMemEval-S knowledge-update** | 冲突专项（过期事实 / 冲突裁决 / 回溯意图） | **72**（= 1a 49 + 1b 7 + 16 待判层），provisional |

## 技术栈（已锁定）

- Python **3.13** 单环境；FastAPI + Pydantic + SQLAlchemy 2 + Alembic
- **MySQL 8**（事实 / 会话 / trace / eval_runs）+ **LanceDB**（向量）+ BM25；向量不进 MySQL
- **LangGraph StateGraph**（不是 LangChain 全家桶；不写 `AgentExecutor` 壳）
- 原生 **function calling** + MCP（`memory_search` / `memory_write` / `memory_forget`）
- React + TypeScript + Vite + SSE；Docker Compose；单 API 副本

## 目录

```text
docs/                     # 要入库的文档（协议、许可、gate、ADR、启动提示词）
dataset/                  # 数据与核验产物（大文件不入库，见 .gitignore）
  v2/                     # LongMemEval-V2 web 子集：questions / 轨迹 / 题图 / 索引 / 核验脚本
  docs/                   # 数据侧清单（_ku78_ids.txt 等）
  archive/
```

## 当前状态

- M0a：已完成（许可 / 版本 / 结构 / 压缩比 / 15 张题图 / 官方 RAG 源码核验）
- **M0b：in progress**
  - G1（15 道带图 `errors-gotchas` 参考答案自洽性）：进行中，产物 `docs/gate_image15.md`
  - V1-KU 72 题标注：待启动（≥7 天日历等待，必须并行）
- **G1 只卡 M3**；M1/M2 工程可并行
- **168 与 72 均未冻结**；153 只作敏感性分析

## 数据与许可边界

- V2 = Apache-2.0（轨迹原文可入库，保留 LICENSE + NOTICE）；**不下载 5.92 GB 轨迹截图包**
- V1-S 的 MIT 只覆盖 benchmark 自身；**session 原文不入库**
- PerLTQA / engram-eval / LoCoMo 等非商用数据不入库
- **API Key 只经 `.env` 读取**，不入库、不进日志、不进对话；`.env.example` 只有占位符

## 运行（尚未实现，M1 起）

TBD —— M1 最小闭环落地后补复现命令。
