import { useEffect, useState } from "react";
import { Alert, Button, Card, Input, Radio, Space, Table, Tabs, Tag, Typography, message } from "antd";
import { api, type ReviewDecision } from "../api";

const { Paragraph, Text } = Typography;

type ConflictFact = { id: string; attribute: string; value: string; valid_from: string; confidence: number };

/** 审核页：冲突裁决（选一个保留、其余失效 + 原因），并展示裁决金标历史。 */
export default function ReviewPage() {
  const [groups, setGroups] = useState<{ entity_id: string; facts: ConflictFact[]; reason?: string }[]>([]);
  const [decisions, setDecisions] = useState<ReviewDecision[]>([]);
  const [kept, setKept] = useState<Record<string, string>>({});
  const [reason, setReason] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = () =>
    Promise.all([api.reviewConflicts(), api.reviewDecisions()])
      .then(([g, d]) => {
        setGroups(g);
        setDecisions(d);
        setError("");
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    void load();
  }, []);

  const decide = async (group: { entity_id: string; facts: ConflictFact[] }) => {
    const keepId = kept[group.entity_id];
    if (!keepId) {
      message.warning("先选择要保留的那一条");
      return;
    }
    setBusy(group.entity_id);
    try {
      await api.createReviewDecision({
        entity_id: group.entity_id,
        kept_fact_id: keepId,
        invalidated_fact_ids: group.facts.filter((f) => f.id !== keepId).map((f) => f.id),
        reason: reason[group.entity_id] ?? "",
      });
      message.success("裁决已记录：保留 1 条，其余标记失效");
      setKept((s) => ({ ...s, [group.entity_id]: "" }));
      setReason((s) => ({ ...s, [group.entity_id]: "" }));
      void load();
    } catch (e) {
      message.error(String(e));
    } finally {
      setBusy(null);
    }
  };

  const conflictColumns = (entity: string) => [
    {
      title: "保留",
      width: 70,
      render: (_: unknown, r: ConflictFact) => (
        <Radio
          checked={kept[entity] === r.id}
          onChange={() => setKept((s) => ({ ...s, [entity]: r.id }))}
        />
      ),
    },
    { title: "属性", dataIndex: "attribute", width: 200 },
    { title: "值", dataIndex: "value" },
    { title: "生效时间", dataIndex: "valid_from", width: 180, render: (v: string) => new Date(v).toLocaleString() },
  ];

  const decisionColumns = [
    { title: "实体", dataIndex: "entity_id", width: 120 },
    { title: "属性", dataIndex: "attribute", width: 180 },
    { title: "保留", dataIndex: "kept_fact_id", width: 110, render: (v: string) => <Text code>{v.slice(0, 8)}</Text> },
    {
      title: "失效",
      dataIndex: "invalidated_fact_ids",
      width: 160,
      render: (v: string[]) => <Space>{v.map((x) => <Text key={x} code>{x.slice(0, 8)}</Text>)}</Space>,
    },
    { title: "原因", dataIndex: "reason", ellipsis: true, render: (v?: string) => v || "—" },
    { title: "时间", dataIndex: "created_at", width: 180, render: (v: string) => new Date(v).toLocaleString() },
  ];

  return (
    <Card title="审核（冲突裁决）" extra={<Button onClick={() => void load()}>刷新</Button>}>
      <Paragraph type="secondary">
        规则：同一实体下「属性关键词重叠」的多个当前值进入审核队列。裁决 = 选一条保留、其余标记失效（不删除），并记录原因与操作者，形成可追溯的金标。
      </Paragraph>
      {error && <Alert type="error" showIcon message="加载失败" description={error} style={{ marginBottom: 12 }} />}

      <Tabs
        items={[
          {
            key: "pending",
            label: `审核（${groups.length}）`,
            children:
              groups.length === 0 ? (
                <Text type="secondary">没有需要审核的冲突 🎉</Text>
              ) : (
                groups.map((g) => (
                  <Card
                    key={g.entity_id}
                    size="small"
                    style={{ marginBottom: 10 }}
                    title={<Space><Text strong>{g.entity_id}</Text><Tag>{g.facts.length} 个当前值</Tag></Space>}
                  >
                    <Paragraph type="secondary" style={{ marginBottom: 8 }}>
                      冲突原因：{g.reason || "同一实体下存在多条语义相近的当前值，需确认哪条有效"}
                    </Paragraph>
                    <Table
                      rowKey="id"
                      size="small"
                      dataSource={g.facts}
                      columns={conflictColumns(g.entity_id)}
                      pagination={false}
                    />
                    <Space style={{ marginTop: 10 }} wrap>
                      <Input
                        placeholder="裁决原因（可选）"
                        value={reason[g.entity_id] ?? ""}
                        onChange={(e) => setReason((s) => ({ ...s, [g.entity_id]: e.target.value }))}
                        style={{ width: 320 }}
                      />
                      <Button type="primary" loading={busy === g.entity_id} onClick={() => void decide(g)}>
                        裁决：保留选中，其余失效
                      </Button>
                    </Space>
                  </Card>
                ))
              ),
          },
          {
            key: "decisions",
            label: `审核历史（${decisions.length}）`,
            children: (
              <Table
                rowKey="id"
                size="small"
                dataSource={decisions}
                columns={decisionColumns}
                pagination={{ pageSize: 12 }}
              />
            ),
          },
        ]}
      />
    </Card>
  );
}
