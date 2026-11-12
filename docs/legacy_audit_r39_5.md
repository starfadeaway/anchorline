# §39.5「历史未修但未复核」逐条复核（2026-11-12）

> 背景：第二十三轮评审 §39.5 列出 26 条"历史记录未修、但当轮未取证"的条目，并明确"不能断言今天仍存在"。
> 本文件对每一条给出**当前代码/文档中的实际状态**与证据位置，用于把这份清单从"未复核"变成"已复核"。
>
> 结论标记：✅ 已修 / ⚠️ 部分修或取舍（写明剩余） / ❓ 无法复核（原文缺失）。

| 编号 | 原描述 | 结论 | 证据 / 剩余 |
|---|---|---|---|
| **F4** | `KNOWN_PCT`/`PP_RAW_WHITELIST` 全局白名单 | ⚠️ 部分 | 百分比/pp 已改文件级（`KNOWN_PCT_BY_FILE`/`PP_RAW_BY_FILE`/`LEGACY_PP_BY_FILE`/`LEGACY_ACC_BY_FILE`）；`LEGACY_P`（p 值）仍全局——p 需跨文件引用，属设计边界 |
| **F9** | 通用实体绑定导致错挂（diet_plan 抢 5K） | ✅ | `tools.py`：多技能时按属性关键词约束归属，单技能按实体；见 G13 同一实现 |
| **F10** | 限流是进程内的 | ✅ | README「API Token 鉴权 / 限流」段明确写"进程内 30 次/分钟、多副本不共享、重启清零" |
| **G10** | `_gen_rate_limited()` 无锁 | ✅ | `api/main.py`：`_GEN_LOCK = threading.Lock()` 模块级，check-then-append 在锁内 |
| **G13** | 通用实体归属 | ✅ | 同 F9 |
| **H1** | `m3_summary` 解读两行脱保护（混代） | ✅ | `_find_comparison` 文件映射 + run3 回落；`m3_summary` 已拆成 run3/run2 两行并加标注 |
| **H7** | 全部超预算时"未注入"提示消失 | ✅ | `build_skills_hint` 返回 note（后改为"未注入 N 个技能"）；`test_budget_note_truncated` 覆盖 |
| **H8** | `LEGACY_REPORTS` 豁免导致 legacy 文件符号不检查 | ⚠️ 取舍 | `reports/d_arm_154.md:1` 已有「第一代产物，已被取代」废弃标注，豁免有依据；该文件符号不检查是明确取舍，不是遗漏 |
| **J7 / I10** | §1 C2 行 `+3.2pp` 无专属绑定 | ✅ | 本轮实测：`+3.2pp → +3.3pp` 注入 **CAUGHT**；文件级 pp 白名单 + 位数精确匹配 |
| **K2** | 预算长名场景仍超支 | ✅ | `build_skills_hint` 按最终拼装字符串（含 note 数量）计算，从尾部丢弃直到符合；测试覆盖 |
| **K5** | 裸 pp 属于别的对比照样放行 | ⚠️ 部分 | 方向检查按"最近前置对比 + 距离/分隔符"绑定裸 pp；全局 diff 集合仍可能放行"别的对比的合法值"——逐格绑定才能根除 |
| **K7** | 食物后缀对用户自定义负向词生效 | ✅ | `_negative_hit` 仅对以「吃」开头的负向词套用后缀豁免 |
| **K10** | `:16` 一行写两个口径 | ✅ | `m3_summary` 已拆为 run3 一行、run2 一行，各自可绑定 |
| **L6** | 技能页 placeholder 仍是竖线 | ✅ | `SkillsPage.tsx` placeholder 改为「如 跑步机,跑步鞋」 |
| **X6** | 导出会话串行、无进度/取消 | ⚠️ 部分 | 已改 10 个/批并发 + `allSettled` + 失败清单；**本轮新增批次进度显示**；取消仍未做 |
| **X12** | Reader/Judge 圆点 `env ? "ok" : "bad"`（空模型名也亮绿） | ✅ | **本轮修复**：`env?.reader_model` / `env?.judge_model`（Embedding/Rerank 早已修） |
| **X26** | StrictMode | ✅ 取舍 | `main.tsx` 注释说明「不包 StrictMode：React 19 dev 双调用会让记忆页明显卡顿」——已解释，非漏修 |
| **X34** | `eval_m2_quality.py` / `verify_reported_numbers.py` 零 argparse | ⚠️ 部分 | **本轮给 `eval_m2_quality.py` 加 `--limit/--out/--md-out/--dry-run`**，默认输出改 `_drafts/`；`verify` 仍只有 `--write`（未改 argparse，属内部工具） |
| **X42** | README 7 张截图死链（`docs/screenshots/` 被 gitignore） | ⚠️ 取舍 | README 已改为**代码块路径清单 + 明确说明"仅本地、不入库"**，不再渲染图片链接（无 404 图片）；但"面试官看不到截图"仍成立——这是用户明确约束（截图不推送），未擅自入库 |
| **D13** | 技能绑定实体的事实注入 value 无上限 | ✅ | `memory_context`：`v[:197] + "…(截断)"` |
| **E16** | 技能草稿输出端无上限 | ✅ | `SkillDraftOut` 四字段 `max_length`（64/128/512/2000） |
| **E17** | 限流只覆盖 1/4 调用点 | ✅ | `/chat`、`/chat/stream`、`/sessions`、`/skills/generate` 均覆盖（生成限流另有 `_GEN_LOCK`） |
| **E18** | 静默截断无标记 / 无聚合上限 / 无测试 | ✅ | 截断标记 + 8000 字符预算 + 3 条技能侧测试 |
| **Z2** | 复现命令覆盖已入库报告 | ✅ | `v1_ku_eval`、`eval_l2_extraction`、`lorekeeper_chunk_*`、`eval_hybrid_arm` 默认输出改 `_drafts/` |
| **Z6** | `m3_2x2` 表格与解读 p 矛盾；`m3_2x2.json` 不在保护网 | ⚠️ 部分 | 表格与解读的 p 已一致（矛盾消除）；但表格仍缺 `B→D`/`C1→D_neighbor`/`D→D_neighbor` 三行，`m3_2x2.json` 只进全局白名单、无专属绑定 |
| **Z8** | json 与 md 的差值符号相反 | ✅ | 本轮新增 `docs/reported_numbers_convention.md`：`diff_a_minus_b = a_file − b_file`，以 `a_file/b_file` 为准 |

## 本轮（C 段）实际改动的代码/文档

1. `frontend/src/pages/ChatPage.tsx`：X12 Reader/Judge 圆点按模型名判断。
2. `scripts/eval_m2_quality.py`：X34 argparse + 默认输出 `_drafts/`。
3. `frontend/src/pages/ReportsPage.tsx`：X6 批次进度显示。
4. `docs/reported_numbers_convention.md`：Z8 符号约定。
5. `docs/legacy_audit_r39_5.md`：本文件。

## 仍需后续（不在本轮范围）

- **K5** 的逐格绑定（需要给每处裸 pp 标注对比键，属报告改写）。
- **Z6** 的表格补行 + `m3_2x2.json` 专属绑定。
- **X42** 若要真正展示截图，需要用户授权入库（脱敏后）或放外部图床。
- **X6** 的取消按钮。
- **F4** 的 `LEGACY_P` 文件级化（p 跨文件引用，收益低于风险）。
