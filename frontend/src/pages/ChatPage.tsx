import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Descriptions, Empty, Input, List, Modal, Typography, message } from "antd";
import { api, type ChatResp, type Fact, type Msg } from "../api";

const { Text } = Typography;

/** 聊天页：左记忆侧栏 + 中聊天 + 右 Trace。 */
export default function ChatPage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [history, setHistory] = useState<Fact[] | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState<ChatResp | null>(null);
  const [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  const loadFacts = () =>
    api
      .facts()
      .then((rows) => {
        setFacts(rows);
        setError("");
      })
      .catch((e) => setError(String(e)));
  useEffect(() => {
    void loadFacts();
  }, []);
  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const next: Msg[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const resp = await api.chat(next);
      setMessages([...next, { role: "assistant", content: resp.answer || "(空回答)" }]);
      setTrace(resp);
      void loadFacts();
    } catch (e) {
      setError(String(e));
      message.error(`发送失败：${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat-grid">
      <Card title="记忆" size="small" className="chat-col" extra={<Button size="small" onClick={() => void loadFacts()}>刷新</Button>}>
        <div className="messages">
          <List
            size="small"
            dataSource={facts}
            locale={{ emptyText: "暂无事实" }}
            renderItem={(f) => (
              <List.Item
                className={`fact-item ${f.valid_to ? "stale" : ""}`}
                onClick={() => api.history(f.id).then(setHistory).catch((e) => message.error(String(e)))}
              >
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>{f.entity_id}.{f.attribute}</Text>
                  <div>{f.value}</div>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {f.conflict_type ?? "—"} · {f.valid_to ? "已失效" : "当前"} · {f.confidence}
                  </Text>
                </div>
              </List.Item>
            )}
          />
        </div>
      </Card>

      <Card title="聊天" size="small" className="chat-col" extra={<Text type="secondary">记忆工具：search / write / forget</Text>}>
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
          {messages.length === 0 && <Empty description="发一条消息，例如：记住我的 5K 最好成绩是 25:50（2023-05-30）" />}
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
          <Empty description="发送消息后显示本轮 trace" />
        ) : (
          <>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="trace_id">{trace.trace_id ?? "—"}</Descriptions.Item>
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

      <Modal open={!!history} onCancel={() => setHistory(null)} footer={null} title="事实历史">
        <List
          size="small"
          dataSource={history ?? []}
          renderItem={(h) => (
            <List.Item>
              <div>
                <Text code>{h.value}</Text>
                <div>
                  <Text type="secondary">{new Date(h.valid_from).toLocaleString()}</Text>
                  {h.valid_to ? <Text type="secondary"> → 失效于 {new Date(h.valid_to).toLocaleString()}</Text> : <Text type="success"> · 当前</Text>}
                </div>
              </div>
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
}
