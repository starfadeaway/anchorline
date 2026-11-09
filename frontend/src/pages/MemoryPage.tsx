import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Drawer, Form, Input, Modal, Space, Table, Tag, Timeline, Typography, message } from "antd";
import { api, type Fact } from "../api";

const { Text } = Typography;

/** 记忆浏览器：表格 + 筛选 + 历史 + 新增/失效。 */
export default function MemoryPage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [q, setQ] = useState("");
  const [history, setHistory] = useState<Fact[] | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [error, setError] = useState("");
  const [form] = Form.useForm();

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

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return facts;
    return facts.filter((f) =>
      [f.entity_id, f.attribute, f.value].some((v) => String(v).toLowerCase().includes(s)),
    );
  }, [facts, q]);

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

  const columns = [
    { title: "实体", dataIndex: "entity_id", width: 160 },
    { title: "属性", dataIndex: "attribute", width: 180 },
    { title: "值", dataIndex: "value" },
    {
      title: "状态",
      width: 120,
      render: (_: unknown, r: Fact) =>
        r.valid_to ? <Tag>已失效</Tag> : <Tag color="green">当前</Tag>,
    },
    { title: "生效时间", dataIndex: "valid_from", width: 180, render: (v: string) => new Date(v).toLocaleString() },
    { title: "置信度", dataIndex: "confidence", width: 80 },
    {
      title: "操作",
      width: 220,
      render: (_: unknown, r: Fact) => (
        <Space>
          <Button
            size="small"
            onClick={() => api.history(r.id).then(setHistory).catch((e) => message.error(String(e)))}
          >
            历史
          </Button>
          <Button
            size="small"
            danger
            disabled={!!r.valid_to}
            onClick={() => {
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
            }}
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
          <Input.Search placeholder="按实体/属性/值过滤" allowClear onChange={(e) => setQ(e.target.value)} style={{ width: 260 }} />
          <Button type="primary" onClick={() => setAddOpen(true)}>新增事实</Button>
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
      <Table rowKey="id" size="small" dataSource={filtered} columns={columns} pagination={{ pageSize: 12 }} />
      {error && (
        <Alert
          type="error"
          showIcon
          closable
          onClose={() => setError("")}
          message="记忆加载失败"
          description={error}
          style={{ marginTop: 12 }}
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
