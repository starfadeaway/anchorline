import { useEffect, useMemo, useState } from "react";
import { Card, Descriptions, Drawer, Input, Table, Tag, Typography, message } from "antd";
import { api, type TraceRow } from "../api";

const { Text } = Typography;

/** Trace 浏览器：全局 trace 列表 + 详情抽屉。 */
export default function TracesPage() {
  const [rows, setRows] = useState<TraceRow[]>([]);
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<TraceRow | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/traces?limit=100")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: TraceRow[]) => setRows(data))
      .catch((e) => {
        setError(String(e));
        message.error("Trace 加载失败");
      });
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) => `${r.query} ${r.id}`.toLowerCase().includes(s));
  }, [rows, q]);

  const columns = [
    { title: "run_id", dataIndex: "id", width: 90 },
    { title: "query", dataIndex: "query", ellipsis: true },
    { title: "Token", dataIndex: "used_tokens", width: 90 },
    { title: "终止", dataIndex: "resolution", width: 100, render: (v?: string) => (v ? <Tag>{v}</Tag> : "—") },
    { title: "时间", dataIndex: "created_at", width: 190, render: (v: string) => new Date(v).toLocaleString() },
  ];

  return (
    <Card
      title="Trace 浏览"
      extra={<Input.Search placeholder="按 query / run_id 过滤" allowClear onChange={(e) => setQ(e.target.value)} style={{ width: 300 }} />}
    >
      {error && <Text type="danger">{error}</Text>}
      <Table
        rowKey="id"
        size="small"
        dataSource={filtered}
        columns={columns}
        pagination={{ pageSize: 15 }}
        onRow={(r) => ({ onClick: () => setDetail(r) })}
      />
      <Drawer open={!!detail} onClose={() => setDetail(null)} title={`Trace #${detail?.id ?? ""}`} width={520}>
        {detail && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="run_id">{detail.id}</Descriptions.Item>
            <Descriptions.Item label="query">{detail.query}</Descriptions.Item>
            <Descriptions.Item label="layers">{detail.layers}</Descriptions.Item>
            <Descriptions.Item label="used_tokens">{detail.used_tokens}</Descriptions.Item>
            <Descriptions.Item label="resolution">{detail.resolution || "—"}</Descriptions.Item>
            <Descriptions.Item label="injected_fact_ids">
              <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{detail.injected_fact_ids || "—"}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="created_at">{new Date(detail.created_at).toLocaleString()}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </Card>
  );
}
