# B 臂错题诊断（12 道，154 题中 B 的错题样本）

- 分类：{'wrong': 10, 'near': 2}
- `empty` = 空答案；`near` = 近似正确但严格判 0；`wrong` = 明显答错。
- `retrieval_miss` 需人工看 top-1 goal 是否与题面相关，这里只列证据。

| qid | type | f1 | gold | answer（前 60） | top-1 goal（前 50） |
|---|---|---|---|---|---|
| `e77d1287` | wrong | 0.0 | Short URL | \boxed{Search comments} | Create a new forum named Cyberpunk, with a descrip |
| `5387d23d` | wrong | 0.0 | heart | \boxed{Yes. In the forum info panel for the selected forum,  | Create a new forum named Cyberpunk, with a descrip |
| `a12b7094` | near | 0.667 | six, Profile, My account, User settings, Block list, Dark mo | \boxed{four, Profile, My account, User settings, Block list} | Change my reddit bio to "I am a robot" |
| `4266cb67` | wrong | 0.5 | Forum creator, Subscriber-only, Viewer-only | \boxed{Forum creator} | Create a new forum named Cyberpunk, with a descrip |
| `91d0775e` | near | 0.667 | A | \boxed{A} | What's the total number of items sold in the most  |
| `07ab3723` | wrong | 0.0 | three | \boxed{four} | Notify Lily Potter in their most recent pending or |
| `06e965cf` | wrong | 0.0 | B | \boxed{A} | Reply to the first reply in this post with "don't  |
| `8f70bc0e` | wrong | 0.0 | Reset | \boxed{Save Review} | Tell me the reasons why customers like Antonia Rac |
| `07d86be1` | wrong | 0.462 | two, My Orders, My Account | \boxed{four, Account Dashboard, Account Information, Address | Compare the payment difference of the last 4 cance |
| `3f366e15` | wrong | 0.333 | Subscribe via RSS | \boxed{RSS feed} | Reply to the first reply in this post with "don't  |
| `0fe2c676` | wrong | 0.0 | C | \boxed{A} | Change my reddit bio to "I am a robot" |
| `d886b018` | wrong | 0.0 | eight | \boxed{six} | Reply to the first reply in this post with "don't  |

> 只抽了错题样本；结论以分类计数 + 人工看表为准，不外推到 154 题全量。