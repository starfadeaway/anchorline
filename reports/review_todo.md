# 评审整改进度（2026-11-11 更新）

> 来源：`Anchorline-项目评审报告-2026-11-11.md`（四轮，含 §17 修复核查）。
> 状态：第一至第四轮的主要问题已处理，剩余项见文末。

## 已完成

### 第一轮（`48d5c7a`）
- [x] P0-6 supersedes 链（已修正为 store 统一失效 + 建链，见 R1/R2 的最终版本）
- [x] P0-5 时区统一（naive 本地时钟；R3 边界归一化）
- [x] P0-7 Docker 环境变量前缀
- [x] P0-8 `numpy` / `mcp` 进 pyproject
- [x] P1-8 `data/exports` 移出版本控制（**R4：历史已用 git filter-repo 清洗并 force push**）
- [x] FE-1 `user.*` 不再全部归宠物
- [x] FE-2 事件日期只写值文本
- [x] FE-3 审核簇 key（稳定哈希 + 后端归属校验）
- [x] N2 词表（工具 schema + 两个评测脚本）
- [x] N7 A/A 不覆盖主跑
- [x] FE-5 SSE/traces 带 token（全部 4 处）

### 第二轮（`6ec84b6` / `b47564e` / `2dd0100`）
- [x] P0-1/P0-2：确定性精确符号翻转 p 值 + `verify_reported_numbers.py` + CI + 报告数字统一
- [x] P0-3/N5：2×2 单变量分解（C1→D 双变量已更正）
- [x] P0-4/N4：噪声底改同臂复跑差
- [x] N1：M2 常数基线；N3：分母台账；N6/N8/N9/N10/N11/N12/N13/N16/N17
- [x] P1-3 部分（lorekeeper 默认路径、CI 密码 secret fallback）

### 第四轮（`385cb87` / `f86aede` / `3b01438` / `9dc608e` / `c73026d` / `bb426ca`）
- [x] R1/R2 supersedes 顺序与倒挂保护 + 3 个单测（M1）
- [x] R3 `valid_from` 边界归一化
- [x] R4 git 历史清洗
- [x] R5 稳定簇 key + 后端归属校验
- [x] R6 测量面/盲标面词表
- [x] R7 traces 全部走统一封装 + N19 4xx 计入错误率
- [x] 脱敏示例导出 `data/exports/sample/`（入库）
- [x] 报告批次标注（run2/run3、2×2 参考臂）
- [x] N15/N25/N26（m2 分列局限、两套口径、量纲）
- [x] FE-4/6/7/8/9/10/11/12/13/14/15/16/17/18/19/20
- [x] P2-1/3/4/5/6/9/10/11/12/13/14/15/16/17/18/19/21/23
- [x] ADR-000（MIT + LICENSE）、ADR-003/004
- [x] 记忆页卡顿（30s 全页重渲染 → RelativeTime 分组件刷新）

## 剩余

- [ ] **§12.2 产品检索臂**：`scripts/eval_hybrid_arm.py` 已写好并在跑（154 题，BM25+向量+RRF+rerank 对照纯向量 D）
- [ ] N14：镜像未打包 `data/lancedb`（Dockerfile 已注明需挂载/重建；未改镜像构建）
- [ ] P2-7/8：token 估算口径（chars/4 vs 单次 max_tokens）——文档说明未统一
- [ ] Docker 实跑（用户决定暂缓）
- [ ] 其余低价值 P2（P2-20 NOTICE、P2-22 重跑 M2 验证词表效果）
