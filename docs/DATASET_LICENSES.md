# 数据集许可与版本核验记录（M0 交付物）

> 核验日期：**2026-11-07**
> 核验环境：Windows 本机（Python 3.13，`D:\Python3135\python.exe`，`urllib` 直连）
> 核验方法：HF Dataset API / GitHub REST API / `raw.githubusercontent.com` 读取 LICENSE 原文 / 本地下载后自行解析计数
> 状态：**本文件中的每一条都是本次实测输出，不是转述。** 复核命令见文末，可原样重跑。

---

## 0. 一个必须先解决的环境问题

本机 **huggingface.co 与 datasets-server.huggingface.co 均连接超时**（WinError 10060），但 **`hf-mirror.com` 通**。

因此所有下载与 API 调用必须走镜像：

```powershell
$env:HF_ENDPOINT = 'https://hf-mirror.com'
# 或在调用时直接用 https://hf-mirror.com/datasets/<id>/resolve/<sha>/<file>
```

不设这个环境变量，W1 的第一步就会卡死。

---

## 1. 逐数据集核验结果

### 1.1 LongMemEval（主集）

| 项 | 实测值 |
|---|---|
| HF dataset id | `xiaowu0162/longmemeval-cleaned` |
| HF revision（已锁定） | `98d7416c24c778c2fee6e6f3006e7a073259d48f` |
| HF license 字段 | `mit` |
| HF gated | `False` |
| lastModified | `2025-09-19T23:48:16Z` |
| 代码仓库 | `github.com/xiaowu0162/LongMemEval` — license **MIT**，1200 stars，last push 2026-05-11 |
| README front-matter | `license: mit` / `language: en` / splits: `longmemeval_oracle` / `longmemeval_s_cleaned` / `longmemeval_m_cleaned` |
| README 说明 | 「replaces the original LongMemEval dataset…removes noisy history sessions that interfere with the answer correctness」 |

**文件清单（实测字节数）**

| 文件 | 字节 | 本项目是否下载 |
|---|---|---|
| `longmemeval_s_cleaned.json` | 277,383,467 | ✅ 下载（主集） |
| `longmemeval_oracle.json` | 15,388,478 | ❌ 不下载（oracle 臂不是本项目对照臂） |
| `longmemeval_m_cleaned.json` | 2,737,100,077 | ❌ **不下载**（2.7 GB，成本与限流不划算） |

> 引用时统一写「LongMemEval-S（`longmemeval_s_cleaned.json`，revision `98d7416c`）」。

### 1.2 LongMemEval-S 自身结构（本地下载后自行解析）

**题数与题型分布（实测）**

| 题型 | 题数 |
|---|---|
| multi-session | 133 |
| temporal-reasoning | 133 |
| **knowledge-update** | **78** |
| single-session-user | 70 |
| single-session-assistant | 56 |
| single-session-preference | 30 |
| **合计** | **500** |

**每题 haystack 规模**

| 范围 | min | median | max |
|---|---|---|---|
| 全 500 题 | 38 | 49 | 62 |
| knowledge-update 78 题 | 39 | 48 | 55 |

**记录字段（实测）**

```
question_id  question_type  question  question_date
answer  answer_session_ids
haystack_dates  haystack_session_ids  haystack_sessions
```

> `answer` 是**标量**（78 题中 76 个 str + 2 个 int），**不是 evidence 列表** —— 官方未提供逐条证据结构。

### 1.3 会话来源构成（实测，许可证风险的关键）

对全部 23,867 个 haystack session 按 `haystack_session_ids` 前缀分类：

| 前缀 | 数量 | 占比 | 性质 |
|---|---|---|---|
| `sharegpt_*` | 6,179 | 25.9% | 第三方语料（ShareGPT） |
| `ultrachat_*` | 6,008 | 25.2% | 第三方语料（UltraChat） |
| `answer_*` | 948 | 4.0% | **benchmark 合成的用户事实 session** |
| 其余（per-question 哈希 id，无统一前缀） | 10,732 | 45.0% | 每题独立生成的干扰 session |

**ShareGPT + UltraChat 合计 = 12,187 / 23,867 = 51.06%。**

knowledge-update 78 题子集：3,706 个 session，其中 `sharegpt_*` 955 个（25.8%），构成比与全量一致。

**结论（三条，写进 ADR）**

1. **LongMemEval 的 MIT 只覆盖 benchmark 自身那一层**；**约 51% 的会话原文来自 ShareGPT / UltraChat，各有独立上游条款，MIT 不能覆盖。**
2. **gold session 全部是 `answer_*` 前缀**（78 题 × 2 个，100%），即**承载用户事实的部分是 benchmark 合成的**，第三方语料只出现在**填充/干扰** session 中。
3. 因此：**session 原文一律不进仓库**（仓库只放下载脚本 + sha256 + 自己的指标与 ID）；但可以放心地**引用 78 题的 `answer_*` session 做分析**，因为它们属 benchmark 自身那一层。

### 1.4 gold session 结构（层 1 标注方案的依据，**2026-11-07 二次修正**）

**78 题每题恰好 2 个 gold session**（`answer_session_ids` 长度为 2，100%），id 前缀 100% 为 `answer_*`（benchmark 合成的用户事实 session），其余约 46 个 session 是干扰项。

> ⚠️ **「按 `haystack_dates` 排序即旧→新」不成立。**
> 按 **haystack 数组索引顺序**判新旧、日期改成**含时刻**比较后，全量 78 题的结果如下。

| 判定 | 题数 | 占比 |
|---|---:|---:|
| answer 唯一在**较晚索引** session（LATER_IDX） | **49** | **62.8%** |
| answer 在**较早索引** session（EARLIER_IDX） | **7** | **9.0%** |
| 两边都有（BOTH） | **2** | **2.6%** |
| 匹配不上（NEITHER） | **20** | **25.6%** |

**精确清单（来自 `order_recheck.json`，不是旧 `strict_match.json`）**

- **EARLIER_IDX 7 道**：`07741c44` `50635ada` `e66b632c` `0ddfec37` `dfde3500` `9bbe84a2` `0977f2af`
- **唯一日期反序 1 道**：`618f13b2`（answer `six` 在较晚索引 `_2`，但 `_2` 的日期 17:45 早于 `_1` 的 22:16；按时间会判错）
- **BOTH 2 道**：`e493bb7c` `10e09553`
- **NEITHER 20 道**：
  - 非拒答 14 道：`6a1eabeb` `d7c942c3` `a1eacc2a` `031748ae` `41698283` `6071bd76` `c4ea545c` `f685340e` `69fee5aa` `06db6396` `42ec0761` `c6853660` `89941a94` `07741c45`
  - `_abs` 拒答 6 道：`6aeb4375_abs` `031748ae_abs` `2698e78f_abs` `2133c1b5_abs` `0ddfec37_abs` `f685340e_abs`

**自动定位与人工量（v2 口径）**

- 自动定位：`49 + 7 = 56 / 78`（71.8%）
- 自动识别拒答：`6 / 78`
- 需人工：`78 - 56 - 6 = 16` 道（BOTH 2 + NEITHER 14）
- 层 1 真正可判分母：`78 - 6 = 72`；其中 `N_a ≥ 49`（现行值）、`N_b ≥ 7`（回溯），其余 16 道人工后再分配。

> ⚠️ 早期 `strict_match.json` 的 `50/8/3/17` 已被 `order_recheck.json` 的 `49/7/2/20` 取代；仓库中只保留后者为权威。

**由此得出的三条结论**

1. **旧/新必须靠内容判定，不能靠日期**；answer 值匹配 + haystack 索引可自动定位 **56/78**，剩余 16 题必须人工。
2. **回溯题不是“时间优先失败”**：7 道 EARLIER_IDX 里有明确回溯问句（`initially` / `previous` / `before` / `first N months`），问的就是旧值；不能把它们算进「过期事实率」。
3. **主集只能暴露“时间优先”的失败，不能干净隔离这条策略**：1 道日期反序、7 道回溯题、来源零方差都会混入；可控消融放 zh30，但 zh30 必须加 reverse 时间戳，否则是送分题。

### 1.5 其他数据集

| 数据集 | 许可（实测） | revision / 元数据 | 代码仓库 | 本项目处置 |
|---|---|---|---|---|
| `shiliu-memory/longmemeval-cn` | HF `license: other`，`license_name: cc-by-4-0-and-upstream-mit`，`license_link` 指向 `NOTICE.txt`；gated=False | sha `0d10ff5baeb2…` | GitHub 存在，3 stars，last push 2026-07-17，**仓库根目录无 LICENSE 文件** | 中文对照；**必须标注「draft、非官方中文版」**；译文与结果属 CC BY 4.0 |
| `ris3abh-11/engram-eval` | HF `license: cc-by-nc-4.0`，gated=False | sha `3b84df655116…` | **`github.com/ris3abh-11/Engram` → 404（无代码仓库）** | **加速器，非唯一 gold**；NC → 不进仓库、不声称商用 |
| `justis-xu/memory-eval-zh` | HF `license: mit`，gated=False | sha `e209267490c6…` | — | 备选中文集 |
| `Elvin-Yiming-Du/PerLTQA` | **`LICENSE.txt` 原文 = CC BY-NC 4.0**（"non-commercial research use only"）；GitHub license API 返回 `NOASSERTION`（未能自动识别，故以文件原文为准） | 7 stars，last push **2025-12-22**（README 记该日修过数据一致性） | `github.com/Elvin-Yiming-Du/PerLTQA` | 原生中文补充；**NC → 不进仓库**；**必须 pin 版本** |
| `snap-research/locomo` | **`LICENSE.txt` 原文 = CC BY-NC 4.0**（GitHub license API 返回 `NOASSERTION`，以文件原文为准） | 1267 stars，last push 2024-08-13 | `github.com/snap-research/locomo` | 次选，NC → 不进仓库 |
| `campfirein/brv-bench` | **仓库根目录无任何许可类文件**（无 LICENSE / LICENSE.txt / NOTICE；GitHub API `license: None`） | 16 stars，last push 2026-05-11 | `github.com/campfirein/brv-bench` | 只作**跑法参考**，不复制其代码进仓库、不作数据来源 |
| `mohammadtavakoli78/BEAM` | GitHub API `license: MIT`（**代码仓库是 MIT**） | 172 stars | `github.com/mohammadtavakoli78/BEAM` | **不引入**（避免 ShareAlike 争议与额外工作量） |

> ⚠️ **两处与第三方来源冲突，以本文件实测为准**：
> ① BEAM 代码仓库实测为 **MIT**（`LICENSE` 原文），而非第三方汇总表所写的 CC BY-SA 4.0（后者描述的是数据集侧）；两者不混用。
> ② `mohammadtavakoli78/BEAM` 才是正确路径，`Mohammadta/BEAM` → **404**。

### 1.6 LongMemEval-V2（2026-05-17，Apache-2.0）

| 项 | 实测值 |
|---|---|
| HF dataset id | `xiaowu0162/longmemeval-v2` |
| HF revision（已锁定） | `f152293e235517d504809563c833d7190b8c713b` |
| HF license 字段 | `apache-2.0` |
| HF gated | `False` |
| dataset lastModified | `2026-05-17` |
| 代码仓库 | `github.com/xiaowu0162/LongMemEval-V2` — **203 stars**，last push **2026-08-09**，**有 leaderboard** |
| 题数 / 轨迹数 | **451 题 / 1,870 条轨迹**（`trajectories.jsonl` 内 web 929 + enterprise 941） |
| domain 分布 | web 240 / enterprise 211 |
| Small 层结构 | `lme_v2_small.json`：451 个 key，每个指向 **100 个 trajectory id**；**全库只有 2 个不同 haystack**（web 240 题共享 1 个 / enterprise 211 题共享 1 个）→ Small 层只需摄入 **200 条**轨迹 |
| Medium 层 | `lme_v2_medium.json`：**447 个不同 haystack** × ~500 轨迹 ≈ **225,500 条**，比 Small 贵约 **1,128×** → 本轮不跑 |
| 运行依赖 | 官方 harness 全线 OpenAI 兼容端点可配（`--reader-base-url` / `--embedding-base-url` / `--evaluator-base-url`）→ **无 GPU 也可跑**；官方 `DATA_CARD` 明写本数据集**不是 live environment replay**，不需要起 WebArena/WorkArena 实例、不需要浏览器 |

**文件清单（实测字节）**

| 文件 | 字节 | 本项目是否下载 |
|---|---|---|
| `trajectories.jsonl` | 1,195,604,539 | ✅ 下载（sha256 `363cec9a…f3c6`，与官方清单一致） |
| `questions.jsonl` | 286,186 | ✅ 下载（sha256 `0a3ae5eb…292b`） |
| `haystacks/lme_v2_small.json` | 822,632 | ✅ 下载（sha256 `9b5301de…6593`） |
| `question_screenshots/*.png`（29 张） | web 15 张合计 **1,708,744 B（1.63 MB）** | ✅ 按需逐张下载，**15 张全部按官方 sha256 校验通过** |
| 截图 tar.gz 压缩包 | 5,916,466,507（enterprise 3,354,163,660 + web 2,562,302,847） | ❌ 不下载（体积大、非能力轴） |
| `haystacks/lme_v2_medium.json` | — | ❌ 不下载 |

> ⚠️ **修正本项目此前的说法**：截图**压缩包 tar.gz 本身**没有官方 checksum 条目，但官方 `checksums.sha256` **逐张给出了 29 个 PNG 的 sha256** → 截图**不必下 5.92 GB 压缩包**，可按需逐张下载并校验（web 15 张仅 1.63 MB）。**5.92 GB 的包里主要是轨迹截图，不是这 29 张题图。**

**完整性校验结果（官方 `checksums.sha256` 共 37 条）**

| 结果 | 文件 |
|---|---|
| ✅ 一致 | `DATA_CARD.md`、`LICENSE`、`SCHEMA.md`、`haystacks/lme_v2_small.json`、`questions.jsonl`、`trajectories.jsonl`、29 张 `question_screenshots/*.png` |
| ❌ **不一致** | `README.md` —— pinned revision 重取仍复现 → 官方仓 checksum 与该 revision 不同步，**记入报告局限章节** |
| — 无条目 | 两个截图 tar.gz 压缩包（但其内部 PNG 逐张有条目，见上） |

**题集结构与分母（`questions.jsonl` 逐行统计；判分函数字段须按 `split("|")[0]` 取前缀，全等匹配会静默得到 0）**

| 口径 | web | enterprise |
|---|---|---|
| 题数 | 240 | 211 |
| abstention（`llm_abstention_checker`） | **72（30.0%）** | 56（26.5%） |
| 非 abstention | **168** | 155 |
| 其中确定性评测 | **154（91.7%）** | 141 |
| 其中 LLM judge | **14** | 14 |
| 带图题 | **15** —— 全部落在 168 内，且**全部是 `errors-gotchas` 题型**（14 道 `llm_gotchas_checker` + 1 道 `norm_phrase_set_match`） | 14 |

**三条处置结论（写进 ADR）**

1. **Apache-2.0 + 自建合成环境** → **轨迹原文可进仓库**（保留 LICENSE 与 NOTICE）。
2. **abstention 剔出主分母、单列报告** —— 理由与 V1 的 `_abs` 同构：`no_retrieval` 在拒答题上天然占优（检索不到 → 输出「信息不足」→ 恰好判对），不剔会稀释主指标约 30%。
3. **带图题不必预先剔除** —— 证据见 `v2/image_q_per_traj.json`、`v2/image_q_probe_small.json`：15 道带图题的**决定性事实词**在 Small 层 web haystack 的 a11y / action / thought 文本中，**14/15 在单条轨迹内即可全覆盖**，第 15 道缺的正是参考答案所要求的**缺席**（"Special Offer" 不存在才对）。
   > 但仍须**单列「带图题（15）」子集**报告：其中 `914ab1d4` 的正确答案（`keyboard_press` / 方向键）来自轨迹的 **action/thought 流**而非 a11y 树 → 对纯 a11y 切片基线（官方 `rag_query_to_slice`）不利，对摄入完整轨迹的本项目有利。
   > ⚠️ 另注：`07a0145f` 的参考答案（总分 `-5`）与其题图上可见的前五条帖子分数（1,1,1,1,8928）**对不上**，这 14 道 judge 题存在参考答案与截图不自洽的风险，M0 需逐题复核后再定是否纳入主指标。

### 1.7 本机网络限制（影响复核方式，必须知道）

| 端点 | 状态 | 替代方案 |
|---|---|---|
| `huggingface.co` | ✗ 超时（WinError 10060） | 用 `hf-mirror.com` |
| `datasets-server.huggingface.co` | ✗ 超时 | 无（改用本地解析） |
| `raw.githubusercontent.com` | ✗ 超时（HTTP 000） | 用 `api.github.com/repos/<repo>/contents/<file>` 取 base64 后本地解码 —— **本文件所有 LICENSE 原文即由此读出** |
| `api.github.com` | ✓ 正常 | — |
| `github.com`（HTML 页） | ✓ 正常 | — |

---

## 2. 仓库分发规则（不变，但本次实测补上了依据）

| 放 | 不放 |
|---|---|
| 下载脚本（含 revision + sha256 校验） | 任何公开集的 session 原文 / 题目原文 |
| 评测脚本与配置 | 公开集派生的重排版 |
| 自建 30 条（自己写的） | PerLTQA / engram-eval / LoCoMo 原文 |
| 自己产出的指标、ID、trace（不含原文） | BEAM 或任何 ShareAlike 内容 |
| **V2 的轨迹原文与官方 id / answer**（Apache-2.0，保留 LICENSE + NOTICE） | V2 截图 tar.gz 压缩包（5.92 GB，不下载） |
| V2 的 29 张题图 PNG（web 15 张 1.63 MB，逐张按官方 sha256 校验） | V1-S 的 session 原文（ShareGPT / UltraChat 来源） |
| `LICENSE` + `NOTICE`（各上游归属与许可声明） | — |
| 本文件（许可核验记录 + 原始输出） | — |

**三条硬规则**

1. **绝不混装不同许可的数据进同一个仓库** —— ShareAlike 会把任何合并产物拖成 CC BY-SA。
2. **session 原文一律不进仓库** —— 51.06% 来自 ShareGPT / UltraChat，有独立上游条款。
3. **非商用数据集不进仓库**，且本项目**不得声称有商业用途**，只作为研究/作品呈现。

> 注：规则 2 针对 **V1-S**；**V2 轨迹原文可进仓库**（Apache-2.0 + 自建合成环境），这是两条不同的许可层，不可混为一谈。

---

## 3. 复核命令（可原样重跑）

```bash
# HF 许可与版本（记得 HF_ENDPOINT=https://hf-mirror.com）
for d in xiaowu0162/longmemeval-cleaned shiliu-memory/longmemeval-cn \
         ris3abh-11/engram-eval justis-xu/memory-eval-zh; do
  curl -s "https://hf-mirror.com/api/datasets/$d" \
    | jq '{id, license: .cardData.license, license_name: .cardData.license_name, sha, gated}'
done

# GitHub 许可
for r in xiaowu0162/LongMemEval Elvin-Yiming-Du/PerLTQA snap-research/locomo \
         mohammadtavakoli78/BEAM campfirein/brv-bench; do
  curl -s "https://api.github.com/repos/$r/license" | jq -r '.license.spdx_id // "NO-FILE"'
done

# 下载主集（锁 revision）
curl -L -o longmemeval_s_cleaned.json \
  https://hf-mirror.com/datasets/xiaowu0162/longmemeval-cleaned/resolve/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json

# 题数与题型分布
python - <<'PY'
import json,collections
d=json.load(open('longmemeval_s_cleaned.json',encoding='utf-8'))
print(len(d), collections.Counter(x['question_type'] for x in d))
PY

# sha256
sha256sum longmemeval_s_cleaned.json

# --- LongMemEval-V2（Apache-2.0）---
V2REV=f152293e235517d504809563c833d7190b8c713b
V2=https://hf-mirror.com/datasets/xiaowu0162/longmemeval-v2/resolve/$V2REV

# 许可与版本
curl -s "https://hf-mirror.com/api/datasets/xiaowu0162/longmemeval-v2" \
  | jq '{id, license: .cardData.license, sha, gated, lastModified}'

# 只取需要的文件（不下 5.92 GB 截图压缩包）
curl -L -o trajectories.jsonl  "$V2/trajectories.jsonl"
curl -L -o questions.jsonl     "$V2/questions.jsonl"
curl -L -o lme_v2_small.json   "$V2/haystacks/lme_v2_small.json"
curl -L -o checksums.sha256    "$V2/checksums.sha256"

# 题图 PNG：逐张下载并按官方 sha256 校验（web 15 张约 1.63 MB）
for f in 0574c69a 07a0145f 1d864942 1e77eb4b 2cc1b9ca 42d13006 626e401e \
         77258cda 81180ae9 910135bb 914ab1d4 b339209c ea361b20 f2b221fd fdeddf71; do
  curl -L -o question_screenshots/$f.png "$V2/question_screenshots/$f.png"
done
sha256sum -c checksums.sha256          # README.md 会 MISMATCH；29 张 PNG 全部 OK

# 分母与图像题统计（判分函数必须按前缀取，全等匹配会静默得到 0）
python - <<'PY'
import json, collections
rows=[json.loads(l) for l in open('questions.jsonl',encoding='utf-8') if l.strip()]
base=lambda q: q["eval_function"].split("|")[0]
img =lambda q: isinstance(q.get("image"),str) and q["image"].strip()!=""
web=[q for q in rows if q["domain"]=="web"]
a   =[q for q in web if base(q)=="llm_abstention_checker"]
n   =[q for q in web if base(q)!="llm_abstention_checker"]
det =[q for q in n   if not base(q).startswith("llm_")]
print("web",len(web),"abstention",len(a),"非abstention",len(n),"确定性",len(det),"judge",len(n)-len(det))
print("全库带图",sum(1 for q in rows if img(q)),"| web 带图",sum(1 for q in web if img(q)),
      "| 其中落在非 abstention 内的",sum(1 for q in n if img(q)))
PY
```

---

## 4. 本文件没有解决、留给后续的

| 项 | 说明 |
|---|---|
| ShareGPT / UltraChat 的**具体**上游条款 | 本文件只证明「51.06% 的 session 来自这两个语料集」；它们的逐条许可需在真要再分发时才需逐条核（当前规则是不再分发，故不阻塞） |
| LongMemEval-CN 译文质量 | 未逐题校验；使用时必须标 draft + 抽题人工复核 |
| engram-eval 的字段与题量 | 仅从 HF 元数据读取（33,263 行 / 575 kB），**未下载、未逐条核对**；W1 若要用需先复核 |
| PerLTQA 的实际题量 | 仅从 README 读取任务划分，未下载 |
| V2 截图 tar.gz 压缩包的完整性 | 压缩包本身**无官方 checksum 条目**（其内部 29 张 PNG 逐张有条目，已校验通过）→ 本项目不下载压缩包，故不阻塞 |
| V2 `README.md` checksum 不一致 | 官方 `checksums.sha256` 与 pinned revision `f152293e…` 的 README 对不上，pinned revision 重取仍复现 → 属官方仓不同步，已记入局限章节 |
| V2 `errors-gotchas` 题的参考答案与题图是否自洽 | 已发现 `07a0145f` 参考答案（总分 -5）与题图可见分数（1,1,1,1,8928）推不出；**14 道 `llm_gotchas_checker` 题均有此风险**，M0 需逐题复核后再定是否纳入主指标 |
