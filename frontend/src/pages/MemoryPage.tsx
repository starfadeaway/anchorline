import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Collapse, Drawer, Form, Input, Modal, Progress, Space, Table, Tag, Timeline, Typography, message } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { api, downloadMarkdown, type Fact, type TraceRow } from "../api";

const { Text } = Typography;

/** 每 30s 刷新一次“现在”，让相对时间活起来。 */
function useNow(intervalMs = 30_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

function formatRelative(iso: string, now: Date): string {
  const diff = now.getTime() - new Date(iso).getTime();
  const abs = Math.abs(diff);
  const past = diff >= 0;
  const suffix = past ? "前" : "后";
  if (abs < 60_000) return "刚刚";
  if (abs < 3_600_000) return `${Math.round(abs / 60_000)} 分钟${suffix}`;
  if (abs < 86_400_000) return `${Math.round(abs / 3_600_000)} 小时${suffix}`;
  if (abs < 30 * 86_400_000) return `${Math.round(abs / 86_400_000)} 天${suffix}`;
  if (abs < 365 * 86_400_000) return `${Math.round(abs / (30 * 86_400_000))} 个月${suffix}`;
  return `${(abs / (365 * 86_400_000)).toFixed(1)} 年${suffix}`;
}

/** 记忆浏览器：按实体分组 + 相对时间 + 资源消耗图表。 */
export default function MemoryPage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [q, setQ] = useState("");
  const [history, setHistory] = useState<Fact[] | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [error, setError] = useState("");
  const [form] = Form.useForm();
  const now = useNow();

  const load = () =>
    api
      .facts()
      .then((rows) => {
        setFacts(rows);
        setError("");
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    void load();
  }, []);

  // 单独加载 trace（资源消耗图）
  useEffect(() => {
    fetch("/api/traces?limit=12")
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: TraceRow[]) => setTraces(rows))
      .catch(() => setTraces([]));
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return facts;
    return facts.filter((f) => [f.entity_id, f.attribute, f.value].some((v) => String(v).toLowerCase().includes(s)));
  }, [facts, q]);

  const groups = useMemo(() => {
    const m = new Map<string, Fact[]>();
    for (const f of filtered) {
      const arr = m.get(f.entity_id) ?? [];
      arr.push(f);
      m.set(f.entity_id, arr);
    }
    return [...m.entries()];
  }, [filtered]);

  const current = facts.filter((f) => !f.valid_to).length;
  const stale = facts.length - current;
  const maxTokens = Math.max(1, ...traces.map((t) => t.used_tokens));

  const submitAdd = async () => {
    try {
      const v = await form.validateFields();
      await api.writeFact(v);
      setAddOpen(false);
      form.resetFields();
      void load();
      message.success("已写入");
    } catch (e) {
      setError(String(e));
      message.error(`写入失败：${String(e)}`);
    }
  };

  const exportMarkdown = () => {
    const lines = [`# Anchorline 记忆导出`, "", `- 导出时间：${new Date().toLocaleString()}`, `- 事实总数：${facts.length}（当前 ${current} / 失效 ${stale}）`, ""];
    for (const [entity, rows] of groups) {
      lines.push(`## ${entity}`, "");
      for (const f of rows) {
        lines.push(`- **${f.attribute}** = ${f.value} ｜ ${f.valid_to ? "已失效" : "当前"} ｜ 生效 ${new Date(f.valid_from).toLocaleString()}${f.valid_to ? ` ｜ 失效 ${new Date(f.valid_to).toLocaleString()}` : ""}`);
      }
      lines.push("");
    }
    downloadMarkdown(`anchorline-memory-${Date.now()}.md`, lines.join("\n"));
    message.success("已导出 Markdown");
  };

  const columns = [
    { title: "属性", dataIndex: "attribute", width: 200 },
    { title: "值", dataIndex: "value" },
    {
      title: "状态",
      width: 90,
      render: (_: unknown, r: Fact) => (r.valid_to ? <Tag>已失效</Tag> : <Tag color="green">当前</Tag>),
    },
    {
      title: "生效时间",
      width: 220,
      render: (_: unknown, r: Fact) => (
        <span>
          {new Date(r.valid_from).toLocaleString()}
          <Text type="secondary" style={{ marginLeft: 6, fontSize: 11 }}>（{formatRelative(r.valid_from, now)}）</Text>
        </span>
      ),
    },
    { title: "置信度", dataIndex: "confidence", width: 80 },
    {
      title: "操作",
      width: 190,
      render: (_: unknown, r: Fact) => (
        <Space>
          <Button size="small" onClick={() => api.history(r.id).then(setHistory).catch((e) => message.error(String(e)))}>历史</Button>
          <Button
            size="small"
            danger
            disabled={!!r.valid_to}
            onClick={() =>
              Modal.confirm({
                title: "把这条记忆标记为失效？",
                content: "不会删除记录；只是标记为「已失效」，历史仍可查看、可追溯。",
                okText: "标记失效",
                cancelText: "取消",
                onOk: async () => {
                  await api.invalidate(r.id);
                  message.success("已标记失效（历史保留）");
                  void load();
                },
              })
            }
          >
            失效
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="记忆浏览器"
      extra={
        <Space>
          <Input.Search placeholder="按实体/属性/值过滤" allowClear onChange={(e) => setQ(e.target.value)} style={{ width: 240 }} />
          <Button type="primary" onClick={() => setAddOpen(true)}>新增事实</Button>
          <Button icon={<DownloadOutlined />} onClick={exportMarkdown}>导出 Markdown</Button>
          <Button onClick={() => void load()}>刷新</Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="这段记忆怎么读？"
        description={
          <div style={{ lineHeight: 1.7 }}>
            <div>· <b>事实</b> = （实体, 属性, 值, 生效时间）。同一实体+属性可以有多条历史值。</div>
            <div>· <b>当前</b> = 这条值仍有效；<b>已失效</b> = 被更新的值替代，或手动标记失效（<b>不删除</b>）。</div>
            <div>· 点<b>历史</b>看同一属性的完整时间线；点<b>失效</b>把当前值标记为失效（会弹确认框）。</div>
            <div>· 聊天时 agent 只会召回「当前」值；被替代的旧值仍可追溯。</div>
          </div>
        }
      />

      <Card size="small" style={{ marginBottom: 12 }} title="概览">
        <Space size={24} wrap>
          <span>事实总数：<Text strong>{facts.length}</Text></span>
          <span>当前：<Text strong style={{ color: "#6abe39" }}>{current}</Text></span>
          <span>失效：<Text strong>{stale}</Text></span>
          <span>实体数：<Text strong>{groups.length}</Text></span>
        </Space>
        <div style={{ marginTop: 10 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>最近 12 轮资源消耗（token）</Text>
          <div className="token-bars">
            {traces.slice().reverse().map((t) => (
              <div key={t.id} className="token-bar" title={`#${t.id} ${t.used_tokens} tokens · ${t.query.slice(0, 40)}`}>
                <div className="token-bar-fill" style={{ height: `${Math.max(6, (t.used_tokens / maxTokens) * 100)}%` }} />
              </div>
            ))}
          </div>
        </div>
        <div className="pie-row">
          <div
            className="pie"
            title={`当前 ${current} / 失效 ${stale}`}
            style={{
              background: `conic-gradient(#6abe39 ${facts.length ? (current / facts.length) * 100 : 0}%, #4a5568 0)`,
            }}
          />
          <div className="pie-legend">
            当前值 <b>{current}</b> 条 · 已失效 <b>{stale}</b> 条<br />
            实体 <b>{groups.length}</b> 个 · 事实总数 <b>{facts.length}</b> 条<br />
            <Text type="secondary" style={{ fontSize: 11 }}>饼图 = 当前值占比（绿色）/ 失效占比（灰）</Text>
          </div>
        </div>
      </Card>

      {error && <Alert type="error" showIcon message="记忆加载失败" description={error} style={{ marginBottom: 12 }} />}

      {groups.map(([entity, rows]) => {
        const cur = rows.filter((f) => !f.valid_to).length;
        return (
          <Card
            key={entity}
            size="small"
            style={{ marginBottom: 10 }}
            title={
              <Space>
                <Text strong>{entity}</Text>
                <Tag>{rows.length} 条</Tag>
                <Tag color="green">{cur} 当前</Tag>
                {rows.length - cur > 0 && <Tag>{rows.length - cur} 失效</Tag>}
              </Space>
            }
          >
            <Progress percent={Math.round((cur / rows.length) * 100)} size="small" strokeColor="#6abe39" showInfo={false} />
            <Table rowKey="id" size="small" dataSource={rows} columns={columns} pagination={false} className="group-table" />
          </Card>
        );
      })}

      {groups.length === 0 && <Text type="secondary">暂无记忆</Text>}

      <Drawer open={!!history} onClose={() => setHistory(null)} title="同一属性的完整历史" width={480}>
        <Timeline
          items={(history ?? []).map((h) => ({
            color: h.valid_to ? "gray" : "green",
            children: (
              <div>
                <Text code>{h.value}</Text>
                <div><Text type="secondary">生效：{new Date(h.valid_from).toLocaleString()}</Text></div>
                <div><Text type="secondary">{h.valid_to ? `失效：${new Date(h.valid_to).toLocaleString()}` : "当前值"}</Text></div>
              </div>
            ),
          }))}
        />
      </Drawer>

      <Modal open={addOpen} onCancel={() => setAddOpen(false)} onOk={() => void submitAdd()} title="新增事实" okText="写入">
        <Form form={form} layout="vertical">
          <Form.Item name="entity_id" label="实体 ID" rules={[{ required: true }]}>
            <Input placeholder="如 user:liu" />
          </Form.Item>
          <Form.Item name="attribute" label="属性" rules={[{ required: true }]}>
            <Input placeholder="如 5K best time" />
          </Form.Item>
          <Form.Item name="value" label="值" rules={[{ required: true }]}>
            <Input placeholder="如 25:50" />
          </Form.Item>
          <Form.Item name="valid_from" label="生效时间（可选，ISO）">
            <Input placeholder="2023-05-30T00:00:00" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
