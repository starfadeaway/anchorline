# V2-web 图像题 G1/G2/G3 gate 记录（15 道 errors-gotchas）

> 目的：在 M3 之前逐题核定 V2-web 主分母 `168 − k`（k ≤ 15）。
> 判据（v0.8 §6.2.1.1）：
> - **G1 参考答案自洽性** —— 参考答案要求的事实能否由题面 + 轨迹事实推出；
> - **G2 语料可得性** —— 答案所需事实在轨迹文本里是否存在（已有实测，见 `v2/image_q_modality_split.json`）；
> - **G3 剔除只认数据缺陷** —— 只有「参考答案不自洽」或「事实不在语料里」才剔除；「某个臂答不对」不是剔除理由。
>
> 硬规则：必须读 **action 之后的 state**；不能只看题图；不能因带图剔除；不能用一个单点观察推断整族。
>
> 数据根：`dataset/`（原 `_m0_verify/` 目录整体迁移到此，旧脚本内的绝对路径已失效）。
> 核验工具：`dataset/v2/gate_g1.py`（只读；按 `traj_offsets.json` 随机 seek，不重扫 1.2 GB）。
> **状态：已完成 —— 15 / 15 全部核验，k = 0，无剔除。**

## 结论

- 15 道 `errors-gotchas`（web 带图题）**全部自洽**，**不剔除**。
- **k = 0** → **主分母 = 168**（M3 按 168 编排，无需等比下调）。
- **`errors-gotchas` 族保留 15 道**，不出现「整族被删」。
- 15 道仍需在报告中**单列子集**（v0.8 §6.2.1：带图题不与普通题混报；其中 `914ab1d4` 的答案只在 `action`/`thought` 流里）。
- 168 由此可进入 M3；但 **168 仍是「本 gate 通过后的 168」**，报告定稿时按同一清单写「主分母 = 168 − 0 = 168」。

## 总表

| # | question_id | 题型 | 参考答案自洽？ | 事实可得性（G2） | 裁定 | 依据摘要 |
|---|---|---|---|---|---|---|
| 1 | `07a0145f` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 题图前五条分数 1,1,1,1,1；轨迹 `2af3e2bb` 踩后每条 `−1`，5 × (−1) = `−5` = 参考答案 |
| 2 | `914ab1d4` | llm_gotchas_checker | **自洽** | 需 action/thought | **保留** | 题图 `Your Rating ★★★☆☆`；`53f7b75e` 6 次 click 4 星均失败；`keyboard_press('ArrowRight')` 后 state 13 的 4 星 radio `checked='true'` |
| 3 | `0574c69a` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | `author:PatientBuilder499` 返回 `No results`，而该作者在 /f/videos 确有 submission |
| 4 | `1d864942` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | Edit Review 页 `Back` → `/admin/review/product/`（标题 `Reviews`），不是 Pending Reviews |
| 5 | `1e77eb4b` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 订单 #000000301 `Order Status = Canceled`；取消后 `Ship` 按钮消失 |
| 6 | `2cc1b9ca` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 搜索页有左侧 `Shop By → Category`；agent 反复切 Price 排序，6209 条不变 |
| 7 | `626e401e` | norm_phrase_set_match | **自洽** | a11y-only 可得 | **保留** | `/forums` 按 submissions：AskReddit 10,041 → **relationship_advice 5,719**；官方归一化把 `_`→空格，预测可同时命中两短语 |
| 8 | `42d13006` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 首页 a11y 中 `Sale` / `Clearance` / `Deals` / `Special` **0 命中**；题图无 sale 模块 |
| 9 | `77258cda` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 保存前 state 4 右侧 `complementary` 无 bio；保存后 state 5 该区出现新 bio 文本 |
| 10 | `81180ae9` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | `Change Billing Address` → `edit/id/26/`，该页同时标 default billing + default shipping |
| 11 | `910135bb` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 订单详情页只展示 Shipping/Billing Address + `Address Book` 链接，无地址编辑入口 |
| 12 | `b339209c` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | Contact Us 页只有 `Phone Number` 输入框，无客服电话（无 tel: / 号码） |
| 13 | `ea361b20` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 订单 177 Items Ordered 恰为 3 件（灯 / TV stand / 沙发）；Reorder 后购物车正是这 3 件 |
| 14 | `f2b221fd` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 题图 `Now Shopping by → Grocery & Gourmet Food`；轨迹显示该分类下没有 `Nutrition Bars & Drinks` |
| 15 | `fdeddf71` | llm_gotchas_checker | **自洽** | a11y-only 可得 | **保留** | 500 → CSRF/rate-limit 错误后，`/f/funny` 列表已出现该帖（带 Edit/Delete） |

---

## 逐题证据

### `07a0145f`（归档）

- 参考答案：`−5`（对 /f/news 前五条各点踩后的合计）。
- 轨迹 `2af3e2bb`：state 2 踩前每条 `1`；state 7 踩完每条 `−1`（U+2212）→ 5 × (−1) = `−5`。
- 结论：**自洽，保留**。

### `914ab1d4`

- 题面：Magento 商品评论页，想打 4 星但点星控件不显示 4 星（题图 `Your Rating ★★★☆☆`）。
- 参考答案：应识别 `keyboard_press` 或明确说按 Right Arrow；继续推荐点击星控件的是错的。
- 轨迹 `53f7b75e`（打 4 星，outcome success）：
  - state 7–12：6 次 `click` 4 星 radio/label，仍为 1 星或 3 星（state 11 `[1711] radio '1 star' checked='true'`；state 12 `[1717] radio '3 stars' focused, checked='true'`）。
  - state 12→13：`keyboard_press('ArrowRight')` → state 13 `[1720] radio '4 stars' focused, checked='true'`。
- 结论：**自洽，保留**。决定性事实只在 action 之后。

### `0574c69a`

- 题面：Postmill 定制论坛，按作者搜某 forum 全部 submission，`author:{name}` 是否好方法。
- 轨迹 `5502a021`：
  - state 1：`/f/videos` 确有 `Submitted by PatientBuilder499`（`t3_10vj2am`）。
  - state 7：`/search?q=author%3APatientBuilder499` → `No results for author:PatientBuilder499`。
  - state 10：纯用户名 → 仍 `No results`；state 14：加 `subreddit:videos` → 仍 `No results`。
- 结论：**自洽，保留**。

### `1d864942`

- 题面：Magento review 编辑页，想回 `Pending Reviews`，点 `Back` 对吗？
- 题图：`Edit Review` 页（Circe Hooded Ice Fleece，Status `Pending`），顶部 `← Back`。
- 轨迹 `639cb243`：
  - state 5：`/admin/review/product/edit/id/353/`，`[687] button '\ue626 Back'`。
  - state 6：点击后 `/admin/review/product/`，`RootWebArea 'Reviews / Customer Reviews / ...'`，`heading 'Reviews'`。
- 结论：`Back` 到 All Reviews（Reviews 列表），不是 Pending Reviews → **自洽，保留**。

### `1e77eb4b`

- 题面：Magento 订单页，老板要填 tracking number，该去哪？
- 题图：订单 `#000000301`，`Order Status = Canceled`。
- 轨迹 `02817e5d`：
  - state 5：取消前 `Order Status = Pending`，有 `[754] button 'Ship'`。
  - state 7：取消后 `Order Status = Canceled`，`You canceled the order.`，`Ship` 按钮消失。
- 结论：**自洽，保留**。

### `2cc1b9ca`

- 题面：One Stop Market 搜索 'wireless earphone' 6209 条，切 `Sort By=Price` 是否最佳。
- 题图：`Items 1-12 of 6209`，左侧 `Shop By → Category`，右上 `Sort By = Relevance`。
- 轨迹 `e45b6563`：state 2 a11y 有 `Shop By` / `Shopping Options` / `Category` / `Beauty & Personal Care( 142 item )`；state 3–50 反复在 `product_list_order=price` 间切换，结果数不变。
- 结论：**自洽，保留**。

### `626e401e`

- 题面：submission 数量第二多的 forum。
- 轨迹 `1ad1af4b` state 1（`/forums`，按 Submissions 排序）：
  - AskReddit `10,041` → **relationship_advice `5,719`** → worldnews `3,464`。
- 评分函数（`official_repo/.../evaluation/qa_eval_metrics.py`）：
  - `normalize_phrase` 把 `-` 与 `_` 都替换为空格；`split_phrases` 按 `,;` 拆答案 → `["relationship","advice"]`；
  - 预测 `relationship_advice` → `relationship advice`，两短语均命中。
- 结论：**自洽，保留**。

### `42d13006`

- 题面：landing page，想找 on sale 的商品，该用哪个模块？没有就说没有。
- 题图：首页只有 `Product Showcases` + 分类导航。
- 证据：首页 a11y（00c06bce state 0，13,799 字符）中 `Sale` / `Clearance` / `Deals` / `Special` **0 命中**。
- 结论：**自洽，保留**（答案 = 没有该功能）。

### `77258cda`

- 题面：bio 编辑页，点 Save 后出现成功横幅但 preview 还在，怎么确认保存成功？要刷新/跳转吗？
- 参考答案：新 bio 出现在右侧 base（sidebar）即确认，同页无需刷新；只依赖横幅/编辑框/preview block 的是错的。
- 轨迹 `2d00b63d`：
  - state 4（保存前）：`[252] complementary` 区只有 Registered / Not whitelisted / Edit biography，**无 bio**。
  - state 5（保存后）：`[260] complementary` 区出现 `StaticText 'Freelance Web Developer'`，同时 `The biography was updated.`。
- 结论：**自洽，保留**。决定性事实只在保存后的 state。

### `81180ae9`

- 题面：Address Book 页，`Change Billing Address` 是否总会覆盖默认 shipping 地址？
- 题图：Default Billing Address 与 Default Shipping Address 是**同一个地址**（Emma Lopez, 101 S San Mateo Dr）。
- 轨迹 `6d5f3f24` / `17c38707`：`Change Billing Address` → `/customer/address/edit/id/26/`，该页 a11y 同时含 `It's a default billing address.` 与 `It's a default shipping address.`。
- 结论：默认 billing 与默认 shipping 是同一地址对象，改 billing 即改 shipping → **自洽，保留**。

### `910135bb`

- 题面：My Account 页，想改某个 past order 的 shipping address，该用哪个模块？没有就说没有。
- 题图：My Account 页（Account Information + Address Book + Default Billing/Shipping）。
- 证据：订单详情页（`/sales/order/view/order_id/169/`）只展示 `Shipping Address` / `Billing Address` + `[1608] link 'Address Book'`，**无地址编辑入口**；Address Book 只管理默认地址与新增地址。
- 结论：**自洽，保留**（答案 = 不能改，指向 My Orders / Address Book 都是错的）。

### `b339209c`

- 题面：Contact Us 表单页，想找客服电话，滚动下去能找到吗？
- 题图：`Contact Us` → `Write Us` 表单（Name / Email / Phone Number / What's on your mind）。
- 证据：contact 页 a11y（6d5f3f24 state 21，`/contact/`）只有 `[1376] textbox 'Phone Number'` 这一输入框，**无任何客服电话号码 / tel: 链接**。
- 结论：**自洽，保留**（滚动无用 / 本站没有客服电话均可接受）。

### `ea361b20`

- 题面：订单详情页，点 `Reorder` 再 `Proceed to Checkout`，系统是否自动用该订单商品走正常结账？
- 题图：订单 `#000000177`（Canceled），`Reorder` 链接，Items Ordered 含 TFCFL 灯、Manhattan Comforts Nacka TV Stand、INLIFE 沙发。
- 轨迹 `aacfe598`：
  - state 5：订单 177 的 Items Ordered = 上述 3 件。
  - state 6：点 `Reorder` → `/checkout/cart/`，购物车里正是这 3 件（agent 误判为「多余商品」并移除，outcome failure）。
- 结论：Reorder 复现的是该订单全部 items；无需先清理/编辑购物车 → **自洽，保留**。

### `f2b221fd`

- 题面：从 landing 页找 `nutrition bars and drinks` 的 root category；当前在 `Grocery & Gourmet Food`，对吗？
- 参考答案：不得把 `Grocery & Gourmet Food` 说成 root category；其他 root 或 `I do not know` 均可接受。
- 题图：搜索 `nutrition bars and drinks` → `Items 1-12 of 4011`，`Now Shopping by → Category: Grocery & Gourmet Food`，左侧子类 Food & Beverage Gifts / Breads & Bakery / Pantry Staples。
- 轨迹 `e43e60e4`：state 0 从 landing 展开 Grocery 菜单找不到；state 19 明确「sidebar 只显示 Grocery 下的 top-level 子类，`Nutrition Bars & Drinks` 不在其中」；随后改试 `cat=77`、`cat=291`。
- 结论：Grocery 下确实不暴露该分类 → **自洽，保留**。

### `fdeddf71`

- 题面：发帖遇到 500，再提交看到截图错误，怎么调查？
- 题图：`Create submission`（funny 论坛）红色错误：`The CSRF token is invalid...` + `You cannot post more. Wait a while...`。
- 轨迹 `2af3e2bb`：
  - state 11：点 Create submission → **500 Internal Server Error**。
  - state 12–13：返回后再提交 → CSRF invalid + rate limit（与题图一致）。
  - state 22：`goto('/f/funny')` → 列表顶部已出现 `We won first place in the costume contest!`（带 Edit/Delete，说明是自己的帖子）→ 实际已发出。
- 结论：去目标 forum 页确认是否已发出 → **自洽，保留**。

---

## 分母台账

- 已核 = **15 / 15**
- k（已剔除） = **0**
- **主分母 = 168 − 0 = 168**
- `errors-gotchas` 族 = 15 道，完整保留
- 168 进入 M3；报告首屏写「主分母 168 − 0；gate 清单见 `docs/gate_image15.md`」

## 方法论备注（本轮发现）

1. `image_q_per_traj.json` 的 `traj` 字段是「决定性事实**词**命中的最佳轨迹」，**不等于**覆盖题面场景的轨迹。例：`1d864942` 给出 `0eef1502`（从未进 review 编辑页），真正证据在 `639cb243`；`81180ae9` / `910135bb` 给出的 `06a17a60` 是「3 月花费」轨迹，与题面无关。→ G1 必须按题面场景另找候选轨迹（`gate_g1.py scan <qid> <port> <pattern>`）。
2. `traj_index.json` 的 `environment` 只有域级 `webarena` / `workarena`，question 的 `environment` 是 `webarena-reddit` / `-cms` / `-onestopshop` → 旧 `gate_evidence.py` 的同环境过滤在 web 上恒为 0。按 `start_url` 端口区分：**9080 = reddit（Postmill）、9082 = onestopshop、9083 = cms（Magento admin）**。
3. `626e401e` 这类 `norm_phrase_set_match` 题，必须读官方 `qa_eval_metrics.py` 判 `_` / `-` 归一化与 `,;` 拆分规则，否则会误判「答案与论坛名不一致」。
