import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Table, Tabs, Tag, Typography, message } from "antd";
import { api, type EvalArm, type LoreKeeperBridge, type ReviewSummary, type TraceRow } from "../api";

const { Paragraph, Text } = Typography;

/** 评测页：臂对比（含说明）+ Trace 浏览 + LoreKeeper 桥接 + 审核裁决。 */
export default function EvalPage() {
  const [rows, setRows] = useState<EvalArm[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [bridge, setBridge] = useState<LoreKeeperBridge | null>(null);
  const [review, setReview] = useState<ReviewSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .evalSummary()
      .then(setRows)
      .catch((e) => {
        setError(String(e));
        message.error(String(e));
      });
    fetch("/api/traces?limit=50")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: TraceRow[]) => setTraces(data))
      .catch(() => setTraces([]));
    api.lorekeeperBridge().then(setBridge).catch(() => setBridge(null));
    api.reviewSummary().then(setReview).catch(() => setReview(null));
  }, []);

  const maxAcc = useMemo(() => Math.max(...rows.map((r) => r.accuracy), 0.01), [rows]);

  const armColumns = [
    { title: "臂", dataIndex: "arm", width: 240 },
    {
      title: "准确率",
      dataIndex: "accuracy",
      width: 120,
      render: (v: number) => <Text strong>{(v * 100).toFixed(1)}%</Text>,
    },
    { title: "题数", dataIndex: "n", width: 80 },
    { title: "来源", dataIndex: "source", width: 220 },
    { title: "备注", dataIndex: "note", render: (v?: string) => v ?? "—" },
  ];

  const traceColumns = [
    { title: "run_id", dataIndex: "id", width: 90 },
    { title: "query", dataIndex: "query", ellipsis: true },
    { title: "Token", dataIndex: "used_tokens", width: 100 },
    { title: "终止", dataIndex: "resolution", width: 100, render: (v?: string) => v || "—" },
    {
      title: "时间",
      dataIndex: "created_at",
      width: 190,
      render: (v: string) => new Date(v).toLocaleString(),
    },
  ];

  return (
    <Card title="评测与可观测">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="口径说明（先读再读表）"
        description={
          <div style={{ lineHeight: 1.8 }}>
            <div>· 固定配置：reader <Text code>deepseek-flash</Text>、embedding <Text code>Qwen3-Embedding-8B</Text>、官方判分、4k 预算、top-6、1 次/题。</div>
            <div>· <b>B</b> = 官方基线（a11y 切片，不去重）；<b>C2</b> = a11y-only + L0 去重；<b>D</b> = 完整轨迹 + L0。</div>
            <div>· 154 题确定性判分；168 题 = 154 + 14 道 LLM judge（prompt 冻结，3 题判分失败已排除）。</div>
            <div>· A/A 噪声底：配对 |Δ| 均值 <b>6.3pp</b>（20 题 × 10 次）；差异需超过它才可称提升。</div>
            <div>· 不进入官方 leaderboard；只报同配置下的相对结果。</div>
          </div>
        }
      />
      {error && <Alert type="error" showIcon message="评测数据加载失败" description={error} style={{ marginBottom: 12 }} />}

      <Tabs
        items={[
          {
            key: "arms",
            label: "臂对比",
            children: (
              <>
                <Table rowKey={(r) => `${r.arm}-${r.source}`} size="small" dataSource={rows} columns={armColumns} pagination={false} />
                <div style={{ marginTop: 12 }}>
                  <Tag color="blue">A/A 噪声底</Tag>
                  <Text type="secondary">配对 |Δ| 均值 6.3pp；20 题单题翻转 5pp，差异需配对检验。</Text>
                </div>
              </>
            ),
          },
          {
            key: "traces",
            label: "Trace 浏览",
            children: (
              <>
                <Paragraph type="secondary">聊天/评测产生的最近 50 条 trace；按时间倒序。工具调用明细可在聊天页右侧 Trace 面板查看。</Paragraph>
                <Table rowKey="id" size="small" dataSource={traces} columns={traceColumns} pagination={{ pageSize: 12 }} />
              </>
            ),
          },
          {
            key: "lorekeeper",
            label: "LoreKeeper 桥接",
            children: bridge ? (
              <>
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 12 }}
                  message={`LoreKeeper 数据集桥接（48 题有 gold_pages，Recall@${bridge.k}）`}
                  description={
                    <div style={{ lineHeight: 1.8 }}>
                      <div>· 数据：LoreKeeper 的 56 题评测集（48 题有 gold_pages）+ 三库 chunk 索引（bge-m3 1024 维，10,843 chunk）。</div>
                      <div>· 查询向量与 LoreKeeper 原生一致（BAAI/bge-m3），只替换检索策略。</div>
                      <div>· <b>chunk 级</b>：纯向量 R@1 0.8542；RRF 单用有害（0.7917）；<b>RRF + rerank 0.8958</b>（+4.17pp）；</div>
                      <div>· <b>页面级重排</b>：按页面聚合后再 rerank，Recall@1 <b>0.854 → 0.917</b>（+3 题、0 反向，+6.25pp；置换检验 p=0.25 → <b>方向正确、样本不足不称显著</b>）。</div>
                    </div>
                  }
                />
                <Text strong>chunk 级检索</Text>
                <Table
                  rowKey="method"
                  size="small"
                  pagination={false}
                  style={{ marginTop: 6, marginBottom: 16 }}
                  dataSource={Object.entries(bridge.chunk ?? {}).map(([method, m]) => ({
                    method: method === "plain_pages" ? "纯向量（LoreKeeper 原生）" : method === "hybrid_pages" ? "Anchorline RRF (+rerank)" : method,
                    ...m,
                  }))}
                  columns={[
                    { title: "方法", dataIndex: "method" },
                    { title: "Recall@1", dataIndex: "recall@1", render: (v: number) => v.toFixed(4) },
                    { title: "Recall@3", dataIndex: "recall@3", render: (v: number) => v.toFixed(4) },
                    { title: "Recall@5", dataIndex: "recall@5", render: (v: number) => v.toFixed(4) },
                    { title: "MRR", dataIndex: "mrr", render: (v: number) => v.toFixed(4) },
                  ]}
                />
                <Text strong>页面级重排</Text>
                <Table
                  rowKey="method"
                  size="small"
                  pagination={false}
                  style={{ marginTop: 6 }}
                  dataSource={Object.entries(bridge.page?.summary ?? {}).map(([method, m]) => ({
                    method: method === "plain_pages" ? "页面聚合（无 rerank）" : method === "hybrid_pages" ? "页面聚合 + 页面级 rerank" : method,
                    ...m,
                  }))}
                  columns={[
                    { title: "方法", dataIndex: "method" },
                    { title: "Recall@1", dataIndex: "recall@1", render: (v: number) => v.toFixed(4) },
                    { title: "Recall@3", dataIndex: "recall@3", render: (v: number) => v.toFixed(4) },
                    { title: "Recall@5", dataIndex: "recall@5", render: (v: number) => v.toFixed(4) },
                    { title: "MRR", dataIndex: "mrr", render: (v: number) => v.toFixed(4) },
                  ]}
                />
                <Paragraph type="secondary" style={{ marginTop: 12 }}>
                  完整报告：<Text code>reports/lorekeeper_bridge.md</Text>；复现：<Text code>scripts/lorekeeper_bridge.py --mode page</Text>。
                </Paragraph>
              </>
            ) : (
              <Paragraph type="secondary">暂无桥接结果（先跑 scripts/lorekeeper_bridge.py）。</Paragraph>
            ),
          },
          {
            key: "review",
            label: "审核裁决",
            children: review ? (
              <>
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 12 }}
                  message={`审核裁决金标：${review.n} 条（累计失效 ${review.invalidated_total} 条事实）`}
                  description="裁决由人工在「审核」页选择保留项 + 原因后写入 review_decisions；这里只读展示，可导出用于冲突专项评测。"
                />
                <Table
                  rowKey="kept_fact_id"
                  size="small"
                  dataSource={review.recent}
                  pagination={false}
                  columns={[
                    { title: "实体", dataIndex: "entity_id", width: 160 },
                    { title: "保留", dataIndex: "kept_fact_id", width: 120, render: (v: string) => <Text code>{v.slice(0, 8)}</Text> },
                    { title: "原因", dataIndex: "reason", ellipsis: true },
                    { title: "时间", dataIndex: "created_at", width: 180, render: (v: string) => (v ? new Date(v).toLocaleString() : "—") },
                  ]}
                />
              </>
            ) : (
              <Paragraph type="secondary">暂无裁决记录（去「审核」页裁决冲突，记录会出现在这里）。</Paragraph>
            ),
          },
        ]}
      />
    </Card>
  );
}
