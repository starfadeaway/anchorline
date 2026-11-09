# LoreKeeper 数据集桥接实验（Anchorline 检索组件 × LoreKeeper 评测集）

> 目的：用 LoreKeeper 的 56 题知识库评测集（其中 **48 题有 `gold_pages`**），验证 Anchorline 的混合检索
> （BM25 + 向量 + RRF + BGE rerank）在**页面级召回**上的表现，与 LoreKeeper 原生的纯向量检索对照。
> 数据源：`<lorekeeper>/backend/app/eval/cases.py`（EvalCase）；索引：`<lorekeeper>/data/lance/kb_<game>_baai-bge-m3_base`。
> 查询向量：`BAAI/bge-m3`（与 LoreKeeper 原生一致，保证公平）。k=5。指标：Recall@k、MRR（页面标题级）。

## 1. 三组对照（48 题）

| 方法 | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| **纯向量**（LoreKeeper 原生口径） | **0.8542** | **0.8750** | 0.8750 | **0.8646** |
| **RRF**（BM25 + 向量，无 rerank） | 0.8542 | 0.8750 | 0.8750 | 0.8646 |
| **RRF + BGE rerank** | 0.8542 | 0.8542 | 0.8750 | 0.8583 |

结论：
1. **融合检索没有带来增益**：RRF 与纯向量完全持平（BM25 没有补回纯向量漏掉的页面）。
2. **rerank 在页面级 gold 口径下轻微有害**：Recall@3 0.875 → 0.8542（少 1 题），MRR 0.8646 → 0.8583。
3. 这不是"Anchorline 检索不行"，而是**重排目标与评测口径不一致**：LoreKeeper 的 gold 是**页面标题**，
   而 rerank 优化的是 chunk 文本与问题的相关性，可能把"相关 chunk 更多但页面标题不同"的页面排前。

## 2. 解释与局限

- 页面级 gold 去重后取 top-5，页面数远少于 chunk 数，**纯向量已经接近天花板**（0.85+），融合空间小。
- 48 题、单次运行、无配对检验；单题翻转 ≈ 2pp，**结论以"持平/无显著增益"为准，不写"提升"**。
- 未对 chunk 级 gold 评测（LoreKeeper 只标页面），因此不能断言"rerank 对 chunk 级无用"。
- LoreKeeper 原生的 A3（打开 rerank）实验口径是 chunk 级 cut20/k3，与本桥接的页面级 k5 不可直接比。

## 4. 页面级重排（方向修正后的实验）

桥接的负结果说明「chunk 相关性 ≠ 页面相关性」。把重排目标改成**页面级**：
向量召回 chunk（top 80）→ 按 `page_title` 聚合（每页取最高分、取前 3 个 chunk 拼接成页面文本）→ 对页面文本做 BGE rerank → 取 top-k 页面。

| 方法 | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| 页面聚合（无 rerank） | 0.8542 | 0.8750 | 0.8750 | 0.8646 |
| **页面聚合 + 页面级 rerank** | **0.9167** | **0.9583** | **0.9792** | **0.9427** |

- 逐题配对（hit@1）：**+3 题命中、0 题反向**，mean diff **+6.25pp**；
- sign-flip 置换检验 **p = 0.252**（48 题、只有 3 个非零配对）→ **方向正确但不显著**；
- 与 chunk 级 rerank 对比（-1 题）相比，页面级重排把方向**反转**为正向，说明机制解释成立（目标对齐）。

> 诚实口径：只能说「页面级重排方向正确、有机制解释」，不能写「显著提升」；要显著性需要扩题或重跑多次。

## 5. 复现

```powershell
# 三组对照（chunk 级）
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --k 5
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --k 5 --no-rerank --out data\eval\lorekeeper_bridge_rrf.json
# 页面级重排
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --mode page --k 5
```


## 4. 下一步（若要提升）

- **页面级重排**：先把 chunk 按页面聚合（取每页最高分 chunk），再对"页面摘要"做 rerank；
- **chunk 级 gold**：让 LoreKeeper 标注到 chunk 或 section，才能公平评估 rerank；
- **查询向量换 Anchorline 口径**（Qwen3-Embedding-8B）重跑：验证向量模型差异，而不是融合策略差异。
