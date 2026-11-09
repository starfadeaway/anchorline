import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Descriptions, Empty, Input, List, Select, Space, Typography, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api, type ChatResp, type ChatSession, type Msg } from "../api";

const { Text } = Typography;

/** 聊天页：左会话列表 + 中聊天 + 右 Trace。会话成组保存，可随时切换。 */
export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState("deepseek");
  const [trace, setTrace] = useState<ChatResp | null>(null);
  const [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  const loadSessions = () =>
    api
      .listSessions()
      .then((rows) => {
        setSessions(rows);
        setError("");
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    void loadSessions();
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startNew = () => {
    setActive(null);
    setMessages([]);
    setTrace(null);
  };

  const openSession = async (id: string) => {
    try {
      const rows = await api.sessionMessages(id);
      setActive(id);
      setMessages(
        rows
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m) => ({ role: m.role as "user" | "assistant", content: m.content })),
      );
      setTrace(null);
    } catch (e) {
      setError(String(e));
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const next: Msg[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const resp = await api.chat(next, { model, sessionId: active });
      setMessages([...next, { role: "assistant", content: resp.answer || "(空回答)" }]);
      setTrace(resp);
      if (!active && resp.session_id) setActive(resp.session_id);
      void loadSessions();
    } catch (e) {
      setError(String(e));
      message.error(`发送失败：${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat-grid">
      <Card
        title="会话"
        size="small"
        className="chat-col"
        extra={<Button size="small" icon={<PlusOutlined />} onClick={startNew}>新建</Button>}
      >
        <div className="messages">
          {sessions.length === 0 && <Empty description="还没有会话，发第一条消息即可创建" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          <List
            size="small"
            dataSource={sessions}
            renderItem={(s) => (
              <List.Item
                className={`session-item ${active === s.id ? "active" : ""}`}
                onClick={() => void openSession(s.id)}
              >
                <div>
                  <div className="session-title">{s.title}</div>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {new Date(s.created_at).toLocaleString()} · {s.message_count} 条
                  </Text>
                </div>
              </List.Item>
            )}
          />
        </div>
      </Card>

      <Card
        title="聊天"
        size="small"
        className="chat-col"
        extra={
          <Space size={6}>
            <Text type="secondary" style={{ fontSize: 12 }}>模型</Text>
            <Select
              size="small"
              value={model}
              onChange={setModel}
              options={[
                { value: "deepseek", label: "DeepSeek" },
                { value: "minimax", label: "MiniMax" },
              ]}
              style={{ width: 110 }}
            />
          </Space>
        }
      >
        {error && (
          <Alert
            type="error"
            showIcon
            closable
            onClose={() => setError("")}
            message="发生错误"
            description={error}
            style={{ marginBottom: 8 }}
          />
        )}
        <div className="messages">
          {messages.length === 0 && (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="发一条消息，例如：记住我的 5K 最好成绩是 25:50（2023-05-30）"
            />
          )}
          {messages.map((m, i) => (
            <div key={i} className="msg">
              <div className="msg-role">{m.role === "user" ? "你" : "Anchorline"}</div>
              <div className="msg-body">{m.content}</div>
            </div>
          ))}
          <div ref={bottom} />
        </div>
        <div className="composer">
          <Input.TextArea
            value={input}
            autoSize={{ minRows: 2, maxRows: 5 }}
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <Button type="primary" loading={busy} onClick={() => void send()}>
            发送
          </Button>
        </div>
      </Card>

      <Card title="Trace" size="small" className="chat-col">
        {!trace ? (
          <Empty description="发送消息后显示本轮 trace" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="trace_id">{trace.trace_id ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="session_id">{trace.session_id ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="steps">{trace.steps}</Descriptions.Item>
              <Descriptions.Item label="stop_reason">{trace.stop_reason}</Descriptions.Item>
              <Descriptions.Item label="tool_calls">{trace.tool_calls.length}</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 12 }}>
              {trace.tool_calls.map((t, i) => (
                <div key={i} className="tool-item">
                  <Text code>{t.name}</Text>
                  <pre>{t.arguments}</pre>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
