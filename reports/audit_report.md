# 项目审计报告（2026-11-10）

> 范围：后端 API / 记忆层 / 检索 / 评测脚本 / 前端 7 页 / CI / e2e / 数据一致性。
> 方法：全端点探测（0 意外非 2xx）、浏览器逐页走查、pytest 82 项、ruff、e2e 9 项、数据分布核对。

## 1. 已修复的 bug（本次审计发现）

| # | 问题 | 影响 | 修复 |
|---|---|---|---|
| 1 | **`/chat/stream` 不落库** | 前端实际走 SSE，消息/会话/主题全不保存；刷新后对话消失 | 抽出 `_ensure_session` + `_persist_turn`，`/chat` 与 `/chat/stream` 共用 |
| 2 | **`/chat/stream` 的 `final.session_id` 永远为 null** | 前端无法定位新建会话、会话列表不刷新 | `_run_agent` 返回 `session_id`，final 用 `sid` |
| 3 | **`/eval/summary` 读旧文件名** | 改名后 B/D/168 全部不显示，只显示了 neighbor（0.6429），前端误导 | 改为 run2/run3 新名，补 C1 与 168 v3 |
| 4 | **会话 topic 永远 None** | 前端主题分组失效；`_gen_topic` 的 `max_tokens=16` 被 reasoning 思考耗尽 | 提到 512 + 关键词兜底；回填了 11 个历史会话 |
| 5 | `facts_index` 用弃用 API `table_names()` | lancedb 新版本告警/未来不兼容 | 兼容 `list_tables()` |
| 6 | MCP 只暴露 3 工具（docstring 与 build_tools 不一致） | MCP 客户端拿不到 kb_search | 补 `kb_search` 工具 + 文档 |
| 7 | e2e 写入的 `user:e2e` 测试数据不清理 | 每次 CI 污染事实表（审计时已累积 27 条 mcp + 4 条 e2e） | e2e `afterAll` 清理 + 手工清掉存量 |
| 8 | e2e-local cleanup 误杀所有 Python3135 进程 | 可能杀掉机器上其它 Python | 改为只停 8000 端口进程 |
| 9 | `include_history` 返回全部失效事实 | 回溯检索噪声大 | 按 query token 过滤 |

## 2. 数据一致性核对

- 端点：全部 200；404 行为正确（fact/session 不存在）。
- 事实表：清理后 9 条（user 8 + user:liu 1），无测试实体残留。
- 会话：12 个，topic 已全部回填（跑步/乒乓球/游泳/遗器效果/…）。
- Trace 228 条、metrics p95 38.6ms、错误率 0%。

## 3. 建议与痛点

**高优先级**
1. **e2e 是 mock 版**：真实模型链路只靠 `REAL_E2E=1` 本地跑一条；CI 不覆盖真实 API（无可控成本与网络）。
2. **评测产物命名仍历史遗留**：`_run2/_run3` 已改，但旧报告里还有 `_v2/_v3` 文本；新读者仍可能误解为数据集版本。
3. **会话删除不删 trace**：孤儿 trace（session_id 指向已删会话）会留库；`/traces` 仍能查到，但按会话查为空。

**中优先级**
4. 测试覆盖 69%：`api/main.py` 仍 ~45%，评测/检索分支仍有盲区（可继续补路由级用例）。
5. `_gen_topic` 每新会话多一次模型调用（~1s 延迟）；可异步或复用首轮回答。
6. 前端 bundle 714KB（antd 未拆），可再 manualChunks。
7. 脚本硬编码路径：`lorekeeper` 路径、`D:\Python3135`（CI 专用）——换机器需改。

**低优先级**
8. Docker 文件未在真实环境验证（虚拟机待部署）。
9. 无鉴权（按决定跳过）；本地单用户。
10. 备份脚本依赖 `mysqldump` 在 PATH（README 未写前置条件）。

## 4. 复现审计

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests scripts run_all.py examples
cd frontend; npm run e2e
curl http://127.0.0.1:8000/eval/summary
```
