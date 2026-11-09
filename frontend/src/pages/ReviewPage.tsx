import { useEffect, useState } from "react";
import { Alert, Button, Card, Modal, Space, Table, Tag, Typography, message } from "antd";
import { api } from "../api";

const { Paragraph, Text } = Typography;

type ConflictFact = { id: string; attribute: string; value: string; valid_from: string; confidence: number };

/** 审核页：同一实体下多个「当前值」的疑似冲突，人工裁决（失效/删除）。 */
export default function ReviewPage() {
  const [groups, setGroups] = useState<{ entity_id: string; facts: ConflictFact[] }[]>([]);
  const [error, setError] = useState("");

  const load = () =>
    api
      .reviewConflicts()
      .then((rows) => {
        setGroups(rows);
        setError("");
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    void load();
  }, []);

  const invalidate = (id: string) =>
    Modal.confirm({
      title: "将这条标记为失效？",
      content: "不删除，保留历史；适合「旧值仍未失效」的情况。",
      okText: "标记失效",
      cancelText: "取消",
      onOk: async () => {
        await api.invalidate(id);
        message.success("已标记失效");
        void load();
      },
    });

  const remove = (id: string) =>
    Modal.confirm({
      title: "彻底删除这条记忆？",
      content: "物理删除，不可恢复。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await api.deleteFact(id);
        message.success("已删除");
        void load();
      },
    });

  const columns = [
    { title: "属性", dataIndex: "attribute", width: 220 },
    { title: "值", dataIndex: "value" },
    { title: "生效时间", dataIndex: "valid_from", width: 190, render: (v: string) => new Date(v).toLocaleString() },
    { title: "置信度", dataIndex: "confidence", width: 80 },
    {
      title: "裁决",
      width: 170,
      render: (_: unknown, r: ConflictFact) => (
        <Space>
          <Button size="small" danger onClick={() => invalidate(r.id)}>失效</Button>
          <Button size="small" type="text" danger onClick={() => remove(r.id)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card title="审核（疑似冲突）" extra={<Button onClick={() => void load()}>刷新</Button>}>
      <Paragraph type="secondary">
        规则：同一实体下存在 ≥2 个「当前值」时进入审核队列（可能是属性名不同导致未自动失效，或确实并存）。裁决后自动刷新。
      </Paragraph>
      {error && <Alert type="error" showIcon message="加载失败" description={error} style={{ marginBottom: 12 }} />}
      {groups.length === 0 ? (
        <Text type="secondary">没有待审核的冲突 🎉</Text>
      ) : (
        groups.map((g) => (
          <Card key={g.entity_id} size="small" style={{ marginBottom: 10 }} title={<Space><Text strong>{g.entity_id}</Text><Tag>{g.facts.length} 个当前值</Tag></Space>}>
            <Table rowKey="id" size="small" dataSource={g.facts} columns={columns} pagination={false} />
          </Card>
        ))
      )}
    </Card>
  );
}
