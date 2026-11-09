import { useEffect, useMemo, useState } from "react";
import { Button, Card, Input, Modal, Space, Table, Tag, Typography, message } from "antd";
import { DeleteOutlined, DownloadOutlined } from "@ant-design/icons";
import { api, downloadMarkdown, type ChatSession, type SessionMessage } from "../api";

const { Paragraph, Text } = Typography;

/** 会话管理（独立功能页）：搜索、导出、删除、统计。 */
export default function SessionsPage() {
  const [rows, setRows] = useState<ChatSession[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = () =>
    api
      .listSessions()
      .then(setRows)
      .catch((e) => message.error(String(e)));

  useEffect(() => {
    void load();
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) => r.title.toLowerCase().includes(s));
  }, [rows, q]);

  const totalMessages = rows.reduce((n, r) => n + r.message_count, 0);

  const exportSession = async (s: ChatSession) => {
    try {
      const msgs = await api.sessionMessages(s.id);
      const lines = [`# 会话：${s.title}`, "", `- session_id：${s.id}`, `- 导出时间：${new Date().toLocaleString()}`, "", "## 对话", ""];
      for (const m of msgs) {
        lines.push(`### ${m.role === "user" ? "我" : "Anchorline"}  ${new Date(m.created_at).toLocaleString()}`, "", m.content, "");
      }
      downloadMarkdown(`anchorline-session-${s.id.slice(0, 8)}.md`, lines.join("\n"));
      message.success("已导出");
    } catch (e) {
      message.error(String(e));
    }
  };

  const remove = (s: ChatSession) =>
    Modal.confirm({
      title: `删除会话「${s.title.slice(0, 24)}」？`,
      content: "会删除该会话的消息记录；记忆事实不受影响。该操作不可撤销。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        setBusy(s.id);
        try {
          await api.deleteSession(s.id);
          message.success("已删除会话");
          void load();
        } catch (e) {
          message.error(String(e));
        } finally {
          setBusy(null);
        }
      },
    });

  const columns = [
    { title: "标题", dataIndex: "title", ellipsis: true },
    { title: "消息数", dataIndex: "message_count", width: 90, render: (v: number) => <Tag>{v}</Tag> },
    { title: "创建时间", dataIndex: "created_at", width: 190, render: (v: string) => new Date(v).toLocaleString() },
    {
      title: "操作",
      width: 180,
      render: (_: unknown, s: ChatSession) => (
        <Space>
          <Button size="small" icon={<DownloadOutlined />} onClick={() => void exportSession(s)}>导出</Button>
          <Button size="small" danger icon={<DeleteOutlined />} loading={busy === s.id} onClick={() => remove(s)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="会话管理"
      extra={<Input.Search placeholder="按标题搜索" allowClear onChange={(e) => setQ(e.target.value)} style={{ width: 280 }} />}
    >
      <Paragraph type="secondary">
        会话总数 <Text strong>{rows.length}</Text>，消息总数 <Text strong>{totalMessages}</Text>。删除会话不会删除已写入的记忆事实。
      </Paragraph>
      <Table rowKey="id" size="small" dataSource={filtered} columns={columns} pagination={{ pageSize: 12 }} />
    </Card>
  );
}
