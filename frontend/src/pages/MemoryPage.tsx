import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Checkbox, Collapse, Drawer, Form, Input, Modal, Space, Table, Tag, Timeline, Tooltip, Typography, message } from "antd";
import { DeleteOutlined, DownloadOutlined, HistoryOutlined, StopOutlined } from "@ant-design/icons";
import { api, downloadMarkdown, type Fact, type TraceRow } from "../api";
import { topicOfText } from "../topics";

const { Text } = Typography;

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

function topicOfFact(f: Fact): string {
  // 实体前缀优先（大模型.* → 模型与配置；user.宠物 → 宠物），否则按属性关键词
  if (/^大模型/.test(f.entity_id)) return "模型与配置";
  if (/^user\.[^:]/.test(f.entity_id)) return "宠物";
  return topicOfText(f.attribute);
}

/** 分段环形图：当前/失效两段，hover 段加粗突起并显示数据；加载时有转圈动画。 */
function Donut({ current, stale, size = 120, label }: { current: number; stale: number; size?: number; label: string }) {
  const total = current + stale;
  const curPct = total ? current / total : 0;
  const [hover, setHover] = useState<"cur" | "stale" | null>(null);
  const R = 40;
  const C = 2 * Math.PI * R;
  const gap = total ? Math.min(4, C * 0.02) : 0;
  const curLen = Math.max(0, C * curPct - gap);
  const staleLen = Math.max(0, C * (1 - curPct) - gap);
  const baseWidth = size > 100 ? 11 : 10;

  return (
    <div className="donut-wrap" style={{ width: size, height: size }} title={`${label}：当前 ${current} 条 / 失效 ${stale} 条`}>
      <svg viewBox="0 0 100 100" className="donut-svg">
        <circle cx="50" cy="50" r={R} fill="none" stroke="transparent" strokeWidth={22} />
        <circle
          className={`arc arc-stale ${hover === "stale" ? "arc-hot" : ""}`}
          cx="50" cy="50" r={R} fill="none"
          stroke="#5b6b85"
          strokeWidth={hover === "stale" ? baseWidth + 5 : baseWidth}
          strokeDasharray={`${staleLen} ${C}`}
          strokeDashoffset={-(curLen + gap * 2)}
          strokeLinecap="round"
          onMouseEnter={() => setHover("stale")}
          onMouseLeave={() => setHover(null)}
        />
        <circle
          className={`arc arc-cur ${hover === "cur" ? "arc-hot" : ""}`}
          cx="50" cy="50" r={R} fill="none"
          stroke="#3ddc97"
          strokeWidth={hover === "cur" ? baseWidth + 5 : baseWidth}
          strokeDasharray={`${curLen} ${C}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          onMouseEnter={() => setHover("cur")}
          onMouseLeave={() => setHover(null)}
        />
      </svg>
      <div className="donut-center">
        {hover === "cur" ? (
          <><b>{current}</b><span>当前</span></>
        ) : hover === "stale" ? (
          <><b>{stale}</b><span>失效</span></>
        ) : (
          <><b>{Math.round(curPct * 100)}%</b><span>当前</span></>
        )}
      </div>
    </div>
  );
}

/** 记忆浏览器：下拉分组 + 组内图表 + 顶部整体图表。 */
export default function MemoryPage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [q, setQ] = useState("");
  const [history, setHistory] = useState<Fact[] | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportSelected, setExportSelected] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [form] = Form.useForm();
  const now = useNow();
  const [hoverBar, setHoverBar] = useState<TraceRow | null>(null);
  const [capacity, setCapacity] = useState<{ limit: number; total_current: number } | null>(null);

  const load = () =>
    api
      .facts()
      .then((rows) => {
        setFacts(rows);
        setError("");
      })
      .then(() => api.capacity().then((c) => setCapacity({ limit: c.limit, total_current: c.total_current })))
      .catch((e) => setError(String(e)));

  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    fetch("/api/traces?limit=12")
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: TraceRow[]) => setTraces(rows))
      .catch(() => setTraces([]));
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    const base = facts.filter((f) => topicOfFact(f) !== "测试数据");
    if (!s) return base;
    // 同时匹配实体/属性/值/主题名（支持搜"跑步""球类"命中整组）
    return base.filter((f) => {
      const topic = topicOfFact(f);
      const hay = `${f.entity_id} ${f.attribute} ${f.value} ${topic}`.toLowerCase();
      return hay.includes(s);
    });
  }, [facts, q]);

  const groups = useMemo(() => {
    const m = new Map<string, Fact[]>();
    for (const f of filtered) {
      const topic = topicOfFact(f);
      if (topic === "测试数据") continue; // 不展示测试数据
      m.set(topic, [...(m.get(topic) ?? []), f]);
    }
    // 组内：越新越前（按生效时间）；组：按组内最新一条倒序
    for (const rows of m.values()) {
      rows.sort((a, b) => new Date(b.valid_from).getTime() - new Date(a.valid_from).getTime());
    }
    return [...m.entries()].sort(
      (a, b) => new Date(b[1][0].valid_from).getTime() - new Date(a[1][0].valid_from).getTime(),
    );
  }, [filtered]);

  const visible = groups.reduce((n, [, rows]) => n + rows.length, 0);
  const current = groups.reduce((n, [, rows]) => n + rows.filter((f) => !f.valid_to).length, 0);
  const stale = visible - current;
  const maxTokens = Math.max(1, ...traces.map((t) => t.used_tokens));

  const invalidateFact = (r: Fact) =>
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
    });

  const deleteFact = (r: Fact) =>
    Modal.confirm({
      title: "彻底删除这条记忆？",
      content: "物理删除，不可恢复（用于控制存储量）。若只想停用请用「失效」。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await api.deleteFact(r.id);
        message.success("已删除");
        void load();
      },
    });

  const submitAdd = async () => {
    try {
      const v = await form.validateFields();
      const res = await api.writeFact(v);
      setAddOpen(false);
      form.resetFields();
      if (res.archived && res.archived > 0) {
        message.warning(`已写入；因超出每实体 ${capacity?.limit ?? 200} 条上限，自动归档 ${res.archived} 条旧记忆（已标记失效，可追溯）`);
      } else {
        message.success("已写入");
      }
      void load();
    } catch (e) {
      setError(String(e));
      message.error(`写入失败：${String(e)}`);
    }
  };

  const exportMarkdown = (topics: string[] = groups.map(([t]) => t)) => {
    const selected = groups.filter(([t]) => topics.includes(t));
    const n = selected.reduce((acc, [, rows]) => acc + rows.length, 0);
    const cur = selected.reduce((acc, [, rows]) => acc + rows.filter((f) => !f.valid_to).length, 0);
    const lines = [`# Anchorline 记忆导出`, "", `- 导出时间：${new Date().toLocaleString()}`, `- 分组：${topics.join("、")}`, `- 事实：${n}（当前 ${cur} / 失效 ${n - cur}）`, ""];
    for (const [topic, rows] of selected) {
      lines.push(`## ${topic}`, "");
      for (const f of rows) {
        lines.push(
          `- **${f.entity_id}.${f.attribute}** = ${f.value} ｜ ${f.valid_to ? "已失效" : "当前"} ｜ 生效 ${new Date(f.valid_from).toLocaleString()}${f.valid_to ? ` ｜ 失效 ${new Date(f.valid_to).toLocaleString()}` : ""}`,
        );
      }
      lines.push("");
    }
    downloadMarkdown(`anchorline-memory-${Date.now()}.md`, lines.join("\n"));
    message.success(`已导出 ${topics.length} 组 Markdown`);
    setExportOpen(false);
  };

  const columns = [
    { title: "实体", dataIndex: "entity_id", width: 90, ellipsis: true },
    { title: "属性", dataIndex: "attribute", width: 120, ellipsis: true },
    { title: "值", dataIndex: "value", width: 300 },
    {
      title: "状态",
      width: 80,
      render: (_: unknown, r: Fact) => (r.valid_to ? <Tag>已失效</Tag> : <Tag color="green">当前</Tag>),
    },
    {
      title: "生效时间",
      width: 150,
      render: (_: unknown, r: Fact) => (
        <span>
          {new Date(r.valid_from).toLocaleString()}
          <Text type="secondary" style={{ marginLeft: 6, fontSize: 11 }}>（{formatRelative(r.valid_from, now)}）</Text>
        </span>
      ),
    },
    {
      title: "操作",
      width: 140,
      render: (_: unknown, r: Fact) => (
        <Space size={8}>
          <Tooltip title="查看历史">
            <Button
              icon={<HistoryOutlined />}
              onClick={() => api.history(r.id).then(setHistory).catch((e) => message.error(String(e)))}
              style={{
                background: "rgba(0, 212, 255, .14)",
                borderColor: "var(--neon)",
                color: "var(--neon)",
              }}
            />
          </Tooltip>
          <Tooltip title={r.valid_to ? "已失效" : "标记失效"}>
            <Button danger icon={<StopOutlined />} disabled={!!r.valid_to} onClick={() => invalidateFact(r)} />
          </Tooltip>
          <Tooltip title="彻底删除">
            <Button danger type="text" icon={<DeleteOutlined />} onClick={() => deleteFact(r)} />
          </Tooltip>
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
          <Button
            danger
            onClick={() =>
              Modal.confirm({
                title: "清空所有已失效记忆？",
                content: "物理删除所有 valid_to 已设置的旧值（当前值保留）。用于控制存储量。",
                okText: "清空",
                okButtonProps: { danger: true },
                cancelText: "取消",
                onOk: async () => {
                  const r = await api.purgeStaleFacts();
                  message.success(`已清理 ${r.deleted} 条失效记忆`);
                  void load();
                },
              })
            }
          >
            清空失效
          </Button>
          <Button icon={<DownloadOutlined />} onClick={() => { setExportSelected(groups.map(([t]) => t)); setExportOpen(true); }}>导出 Markdown</Button>
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
            <div>· <b>当前</b> = 仍有效；<b>已失效</b> = 被新值替代或手动标记（不删除）。</div>
            <div>· 点<b>历史</b>看时间线；点<b>失效</b>标记当前值（会弹确认框）；展开分组看每组明细。</div>
          </div>
        }
      />

      {capacity && capacity.limit > 0 && (
        <Alert
          type={capacity.total_current >= capacity.limit * 0.9 ? "warning" : "success"}
          showIcon
          style={{ marginBottom: 12 }}
          message={capacity.total_current >= capacity.limit * 0.9 ? "记忆容量接近上限" : "记忆容量正常"}
          description={`当前值 ${capacity.total_current} 条 / 每实体上限 ${capacity.limit} 条。超出上限时自动归档最旧或最低置信度的值（标记失效，不删除、可追溯）。`}
        />
      )}

      <Card size="small" style={{ marginBottom: 12 }} title="整体概览">
        <div className="overview">
          <Donut current={current} stale={stale} size={132} label="全部" />
          <div className="overview-legend">
            <div><span className="legend-dot green" /> 当前值 <b>{current}</b> 条</div>
            <div><span className="legend-dot gray" /> 已失效 <b>{stale}</b> 条</div>
            <div>事实总数 <b>{visible}</b> 条 · 分组 <b>{groups.length}</b> 个</div>
            <div className="overview-note">环形图 = 当前值占比；鼠标悬停可看明细</div>
          </div>
          <div className="overview-bars">
            <div className="bars-head">
              <Text type="secondary" style={{ fontSize: 12 }}>最近 12 轮对话的 token 消耗</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>峰值 {maxTokens} tokens</Text>
            </div>
            <div className="token-bars">
              {traces.slice().reverse().map((t) => (
                <div
                  key={t.id}
                  className="token-bar"
                  onMouseEnter={() => setHoverBar(t)}
                  onMouseLeave={() => setHoverBar(null)}
                >
                  <div className="token-bar-fill" style={{ height: `${Math.max(8, (t.used_tokens / maxTokens) * 100)}%` }} />
                </div>
              ))}
            </div>
            {hoverBar ? (
              <div className="bar-tip">
                #{hoverBar.id} · {hoverBar.used_tokens} tokens · {new Date(hoverBar.created_at).toLocaleTimeString()}
                <div className="bar-tip-query">{hoverBar.query.slice(0, 40)}</div>
              </div>
            ) : (
              <div className="bar-tip muted">悬停柱子查看：run、token、时间、query（越高表示该轮占用的记忆/上下文越多）</div>
            )}
          </div>
        </div>
      </Card>

      {error && <Alert type="error" showIcon message="记忆加载失败" description={error} style={{ marginBottom: 12 }} />}

      {groups.length === 0 ? (
        <Text type="secondary">暂无记忆</Text>
      ) : (
        <Collapse
          defaultActiveKey={groups.map(([t]) => t)}
          items={groups.map(([topic, rows]) => {
            const cur = rows.filter((f) => !f.valid_to).length;
            const st = rows.length - cur;
            return {
              key: topic,
              label: (
                <Space size={10}>
                  <Text strong>{topic}</Text>
                  <Tag>{rows.length} 条</Tag>
                  <Tag color="green">{cur} 当前</Tag>
                  {st > 0 && <Tag>{st} 失效</Tag>}
                </Space>
              ),
              children: (
                <div className="group-body">
                  <div className="group-chart">
                    <Donut current={cur} stale={st} size={84} label={topic} />
                    <div className="group-chart-legend">
                      当前占比 <b>{rows.length ? Math.round((cur / rows.length) * 100) : 0}%</b>
                    </div>
                  </div>
                  <Table rowKey="id" size="small" dataSource={rows} columns={columns} pagination={false} className="group-table" tableLayout="fixed" scroll={{ x: 880 }} />
                </div>
              ),
            };
          })}
        />
      )}

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

      <Modal open={exportOpen} onCancel={() => setExportOpen(false)} title="选择要导出的分组" okText="导出选中" onOk={() => exportMarkdown(exportSelected)}>
        <Checkbox.Group
          style={{ display: "flex", flexDirection: "column", gap: 8 }}
          options={groups.map(([t, rows]) => ({ label: `${t}（${rows.length} 条）`, value: t }))}
          value={exportSelected}
          onChange={(v) => setExportSelected(v as string[])}
        />
      </Modal>

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
          <Form.Item name="valid_from" label="事件日期（可选；生效时间仍按记录时间）">
            <Input placeholder="2023-05-30T00:00:00" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
