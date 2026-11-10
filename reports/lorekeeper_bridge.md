# LoreKeeper 数据集桥接实验（Anchorline 检索组件 × LoreKeeper 评测集）

> 目的：用 LoreKeeper 的 56 题知识库评测集（其中 **48 题有 `gold_pages`**），验证 Anchorline 的混合检索
> （BM25 + 向量 + RRF + BGE rerank）在**页面级召回**上的表现，与 LoreKeeper 原生的纯向量检索对照。
> 数据源：`<lorekeeper>/backend/app/eval/cases.py`（EvalCase）；索引：`<lorekeeper>/data/lance/kb_<game>_baai-bge-m3_base`。
> 查询向量：`BAAI/bge-m3`（与 LoreKeeper 原生一致，保证公平）。k=5。指标：Recall@k、MRR（页面标题级）。

## 1. 三组对照（48 题）

| 方法 | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| **纯向量**（LoreKeeper 原生口径） | 0.8542 | 0.8750 | 0.8750 | 0.8646 |
| **RRF**（BM25 + 向量，无 rerank） | 0.7917 | 0.8542 | 0.8958 | 0.8333 |
| **RRF + BGE rerank** | **0.8958** | **0.8958** | **0.8958** | **0.8958** |

结论：
1. **RRF 单用有害**（R@1 0.8542 → 0.7917）：BM25 噪声把页面排序拉低。
2. **rerank 是关键**：RRF + rerank 恢复到 **0.8958**（比纯向量 R@1 +4.17pp）。
3. 修复说明：早期版本融合里的 BM25 分支用"行号"而非 chunk id，导致 BM25 被静默丢弃、得出"融合与纯向量持平"的错误结论；修复后重跑得到上表。**旧结论作废。**

## 2. 解释与局限

- 页面级 gold 去重后取 top-5，页面数远少于 chunk 数，融合空间有限但仍有效（+4.17pp）。
- 48 题、单次运行、无配对检验；单题翻转 ≈ 2pp，**不写"显著提升"**。
- chunk 级 gold 为自动生成（见 §6），只能作机制参考，不能当人工标注结论。
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

## 5. 换向量口径（Qwen3-Embedding-8B vs bge-m3）

用 Anchorline 的 `Qwen/Qwen3-Embedding-8B` 重新嵌入 LoreKeeper 的全部 10,843 个 chunk（`scripts/lorekeeper_reembed.py`），
与 LoreKeeper 原生的 `BAAI/bge-m3` 在同一批 48 题上对照（查询向量与索引保持一致）：

| 向量模型 | 检索口径 | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|
| bge-m3 | 纯向量（chunk 去重） | 0.8542 | 0.8750 | 0.8750 | 0.8646 |
| bge-m3 | RRF + rerank（chunk） | **0.8958** | 0.8958 | 0.8958 | 0.8958 |
| bge-m3 | 页面聚合 + rerank | **0.9167** | 0.9583 | 0.9792 | 0.9427 |
| Qwen3-8B | 纯向量（chunk 去重） | 0.7917 | 0.8542 | 0.8750 | 0.8201 |
| Qwen3-8B | RRF + rerank（chunk） | **0.9167** | 0.9167 | 0.9167 | 0.9167 |
| Qwen3-8B | 页面聚合 + rerank | **0.9167** | 0.9375 | 0.9375 | 0.9271 |

结论：
1. **在这个中文游戏 wiki 场景，bge-m3 的纯向量强于 Qwen3-8B**（0.8542 vs 0.7917）；换向量模型不是提升手段。
2. **融合的收益取决于基线强弱**：Qwen3 弱基线上 RRF+rerank 增益更大（0.7917 → 0.9167，+12.5pp），bge-m3 强基线上 +4.17pp（0.8542 → 0.8958）。
3. **页面级重排对两种向量都有效**，且弱基线增益更大（Qwen3 +12.5pp、bge-m3 +6.25pp）——支持「目标对齐」机制（chunk 相关性 ≠ 页面相关性）。

## 6. chunk 级 gold（自动生成）与 chunk 级评测

LoreKeeper 只标到页面。为评估 rerank 在 chunk 级的公平性，用 **BM25 自动生成**每页的 gold chunk
（问题分词 vs 页内各 chunk 分词，取分最高者；`scripts/lorekeeper_chunk_gold.py --by bm25`），
再用 `scripts/lorekeeper_chunk_eval.py` 对比三种 chunk 级检索（48 题，k=5）：

| 方法 | Recall@1 | Recall@3 | Recall@5 |
|---|---|---|---|
| 纯向量（chunk） | 0.7292 | 0.7917 | 0.7917 |
| RRF（BM25 + 向量） | 0.7292 | 0.8333 | 0.8750 |
| RRF + BGE rerank | **0.7708** | 0.8125 | 0.8333 |

- rerank 在 chunk 级 **R@1 +4.17pp**，但 R@3/R@5 略低；
- 自动 gold 由 BM25 生成，对 BM25 路存在循环偏差，**无法完全消除**；结论只作机制参考，不能替代人工 chunk 标注；
- 另用"向量相似度"生成的 gold 版本（`lorekeeper_chunk_gold.json`）会让纯向量天然占优，已弃用。

## 7. 复现

```powershell
# chunk 级三组对照（bge-m3）
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --k 5
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --k 5 --no-rerank --out data\eval\lorekeeper_bridge_rrf.json
# 页面级重排（bge-m3）
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --mode page --k 5
# 换向量口径（Qwen3-8B）
.venv\Scripts\python.exe scripts\lorekeeper_reembed.py
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --mode chunk --embedder qwen8b --k 5
.venv\Scripts\python.exe scripts\lorekeeper_bridge.py --mode page --embedder qwen8b --k 5
# chunk 级（自动 gold）
.venv\Scripts\python.exe scripts\lorekeeper_chunk_gold.py --by bm25
.venv\Scripts\python.exe scripts\lorekeeper_chunk_eval.py --k 5 --gold data\eval\lorekeeper_chunk_gold_bm25.json
```

## 8. 下一步

- **人工 chunk 级 gold**：让 LoreKeeper 标到 chunk/section，才能对 rerank 下结论；
- **页面级重排**：已做（§4），是目前最强（0.9167）；
- **多轮/多预算**：单次 48 题不足以做显著性，扩题或重跑。
