import { useEffect, useMemo, useState } from "react";
import { Card, Col, Descriptions, Row, Statistic, Table, Tag, Typography, message } from "antd";
import { api, type ApiMetrics, type ChatSession, type SettingsOut, type TraceRow } from "../api";

const { Paragraph, Text } = Typography;

/** 监控页：服务/DB 状态、真实请求指标（延迟分位数/错误率/QPS）、最近 trace。 */
export default function MonitorPage() {
  const [health, setHealth] = useState<{ status: string; db: boolean } | null>(null);
  const [env, setEnv] = useState<SettingsOut | null>(null);
  const [metrics, setMetrics] = useState<ApiMetrics | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(String(e)));
    api.metrics().then(setMetrics).catch(() => setMetrics(null));
    api.settings().then(setEnv).catch(() => setEnv(null));
    api.listSessions().then(setSessions).catch(() => setSessions([]));
    api
      .listTraces(50)
      .then((rows) => setTraces(rows))
      .catch(() => setTraces([]));
  }, []);

  const avgTokens = useMemo(
    () => (traces.length ? Math.round(traces.reduce((n, t) => n + t.used_tokens, 0) / traces.length) : 0),
    [traces],
  );
  const totalMessages = sessions.reduce((n, s) => n + s.message_count, 0);
  const lastTrace = traces[0];

  const columns = [
    { title: "run_id", dataIndex: "id", width: 80 },
    { title: "query", dataIndex: "query", ellipsis: true },
    { title: "Token", dataIndex: "used_tokens", width: 90 },
    { title: "步数", dataIndex: "steps", width: 70, render: (v?: number) => v || "—" },
    { title: "终止", dataIndex: "resolution", width: 90, render: (v?: string) => (v ? <Tag>{v}</Tag> : "—") },
    { title: "时间", dataIndex: "created_at", width: 180, render: (v: string) => new Date(v).toLocaleString() },
  ];

  return (
    <Card title="系统监控">
      <Paragraph type="secondary">
        数据来自 <Text code>/health</Text>、<Text code>/metrics</Text>（最近 1000 次真实请求的延迟分位数/错误率/QPS）、
        <Text code>/sessions</Text> 与 <Text code>/traces</Text>。
      </Paragraph>
      {error && <Paragraph type="danger">{error}</Paragraph>}
      <Row gutter={[12, 12]} style={{ marginBottom: 14 }}>
        <Col span={4}><Card size="small"><Statistic title="服务" value={health?.status ?? "—"} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="数据库" value={health?.db ? "正常" : "异常"} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="p50 延迟" value={metrics?.p50_ms ?? 0} suffix="ms" /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="p95 延迟" value={metrics?.p95_ms ?? 0} suffix="ms" /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="错误率" value={((metrics?.error_rate ?? 0) * 100).toFixed(2)} suffix="%" /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="QPS" value={metrics?.qps ?? 0} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="采样请求" value={metrics?.n ?? 0} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="会话数" value={sessions.length} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="消息数" value={totalMessages} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="trace（最近50）" value={traces.length} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="平均 token" value={avgTokens} /></Card></Col>
      </Row>

      <Card size="small" title="运行配置" style={{ marginBottom: 12 }}>
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="reader">{env?.reader_model ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="judge">{env?.judge_model ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="embedding">{env?.embedding_model ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="rerank">{env?.rerank_model ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="MiniMax">{env?.minimax_model ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="最近一轮">{lastTrace ? `${lastTrace.used_tokens} tokens · ${lastTrace.resolution ?? "—"}` : "—"}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Table rowKey="id" size="small" dataSource={traces} columns={columns} pagination={{ pageSize: 10 }} />
    </Card>
  );
}
