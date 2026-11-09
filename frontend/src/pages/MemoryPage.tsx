import { useEffect, useMemo, useState } from "react";
import { Button, Card, Drawer, Form, Input, Modal, Space, Table, Tag, Timeline, Typography, message } from "antd";
import { api, type Fact } from "../api";

const { Text } = Typography;

/** 记忆浏览器：表格 + 筛选 + 历史 + 新增/失效。 */
export default function MemoryPage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [q, setQ] = useState("");
  const [history, setHistory] = useState<Fact[] | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [form] = Form.useForm();

  const load = () => api.facts().then(setFacts).catch((e) => message.error(String(e)));
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
    const v = await form.validateFields();
    await api.writeFact(v);
    setAddOpen(false);
    form.resetFields();
    void load();
    message.success("已写入");
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
            onClick={async () => {
              await api.invalidate(r.id);
              void load();
              message.success("已标记失效（不删除）");
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
      <Table rowKey="id" size="small" dataSource={filtered} columns={columns} pagination={{ pageSize: 12 }} />

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
