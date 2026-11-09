import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Card, Descriptions, Empty, Input, List, message, Segmented, Space, Tooltip, Typography } from "antd";
import { DownloadOutlined, PlusOutlined } from "@ant-design/icons";
import { api, downloadMarkdown, type ChatResp, type ChatSession, type Msg, type TraceRow } from "../api";

const { Text } = Typography;

function groupSessions(sessions: ChatSession[]): [string, ChatSession[]][] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today.getTime() - 86_400_000);
  const groups: Record<string, ChatSession[]> = { 今天: [], 昨天: [], 更早: [] };
  for (const s of sessions) {
    const d = new Date(s.created_at);
    if (d >= today) groups["今天"].push(s);
    else if (d >= yesterday) groups["昨天"].push(s);
    else groups["更早"].push(s);
  }
  return Object.entries(groups).filter(([, v]) => v.length > 0);
}

function parseToolCalls(raw: string | null): { name: string; arguments: string }[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw) as { name?: string; arguments?: unknown }[];
    if (!Array.isArray(arr)) return [];
    return arr.map((x) => ({ name: String(x.name ?? ""), arguments: typeof x.arguments === "string" ? x.arguments : JSON.stringify(x.arguments ?? {}) }));
  } catch {
    return [];
  }
}

/** 聊天页：左会话列表（按日期分组）+ 中聊天 + 右 Trace（按会话持久化）。 */
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

  const grouped = useMemo(() => groupSessions(sessions), [sessions]);

  const fromTraceRow = (row: TraceRow, sessionId: string): ChatResp => ({
    answer: "",
    stop_reason: row.resolution ?? "",
    steps: 0,
    tool_calls: parseToolCalls(row.injected_fact_ids),
    trace_id: row.id,
    session_id: sessionId,
  });

  const loadSession = async (id: string) => {
    try {
      const rows = await api.sessionMessages(id);
      setActive(id);
      setMessages(
        rows
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m) => ({ role: m.role as "user" | "assistant", content: m.content, created_at: m.created_at })),
      );
      const traces = await api.sessionTraces(id);
      setTrace(traces.length ? fromTraceRow(traces[0], id) : null);
    } catch (e) {
      setError(String(e));
    }
  };

  const startNew = () => {
    setActive(null);
    setMessages([]);
    setTrace(null);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const next: Msg[] = [...messages, { role: "user", content: text, created_at: new Date().toISOString() }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const resp = await api.chat(next, { model, sessionId: active });
      setMessages([
        ...next,
        { role: "assistant", content: resp.answer || "(空回答)", created_at: new Date().toISOString() },
      ]);
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

  const exportMarkdown = () => {
    const title = sessions.find((s) => s.id === active)?.title ?? "新会话";
    const lines = [`# 会话：${title}`, "", `- 导出时间：${new Date().toLocaleString()}`, `- session_id：${active ?? "（未保存）"}`, "", "## 对话", ""];
    for (const m of messages) {
      lines.push(`### ${m.role === "user" ? "我" : "Anchorline"}  ${m.created_at ? new Date(m.created_at).toLocaleString() : ""}`, "", m.content, "");
    }
    if (trace) {
      lines.push("## Trace", "", `- trace_id：${trace.trace_id ?? "—"}`, `- steps：${trace.steps}`, `- stop_reason：${trace.stop_reason}`, "", "| 工具 | 参数 |", "|---|---|");
      for (const t of trace.tool_calls) lines.push(`| ${t.name} | \`${t.arguments.replace(/\|/g, "/")}\` |`);
    }
    downloadMarkdown(`anchorline-${(active ?? "new").slice(0, 8)}-${Date.now()}.md`, lines.join("\n"));
    message.success("已导出 Markdown");
  };

  return (
    <div className="chat-grid">
      <Card
        title="会话"
        size="small"
        className="chat-col"
        extra={
          <Space size={4}>
            <Button size="small" icon={<PlusOutlined />} onClick={startNew}>新建</Button>
            <Tooltip title="导出当前会话 Markdown">
              <Button size="small" icon={<DownloadOutlined />} onClick={exportMarkdown} />
            </Tooltip>
          </Space>
        }
      >
        <div className="messages">
          {sessions.length === 0 && <Empty description="还没有会话，发第一条消息即可创建" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          {grouped.map(([label, rows]) => (
            <div key={label} className="session-group">
              <div className="session-group-title">{label} · {rows.length}</div>
              <List
                size="small"
                dataSource={rows}
                renderItem={(s) => (
                  <List.Item
                    className={`session-item ${active === s.id ? "active" : ""}`}
                    onClick={() => void loadSession(s.id)}
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
          ))}
        </div>
      </Card>

      <Card
        title="聊天"
        size="small"
        className="chat-col"
        extra={
          <Segmented
            size="small"
            value={model}
            onChange={(v) => setModel(String(v))}
            options={[
              { label: "DeepSeek", value: "deepseek" },
              { label: "MiniMax", value: "minimax" },
            ]}
          />
        }
      >
        {error && (
          <Alert type="error" showIcon closable onClose={() => setError("")} message="发生错误" description={error} style={{ marginBottom: 8 }} />
        )}
        <div className="messages">
          {messages.length === 0 && (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="发一条消息，例如：记住我的 5K 最好成绩是 25:50（2023-05-30）" />
          )}
          {messages.map((m, i) => (
            <div key={i} className="msg msg-enter">
              <div className="msg-role">
                {m.role === "user" ? "你" : "Anchorline"}
                {m.created_at && <span className="msg-time">{new Date(m.created_at).toLocaleTimeString()}</span>}
              </div>
              <div className="msg-body">{m.content}</div>
            </div>
          ))}
          <div ref={bottom} />
        </div>
        <div className="composer">
          <Input.TextArea
            value={input}
            autoSize={{ minRows: 2, maxRows: 6 }}
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <Button type="primary" loading={busy} onClick={() => void send()}>发送</Button>
        </div>
      </Card>

      <Card
        title="Trace"
        size="small"
        className="chat-col"
        extra={active ? <Text type="secondary" style={{ fontSize: 11 }}>按会话保存</Text> : null}
      >
        {!trace ? (
          <Empty description="发送消息后显示本轮 trace" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="trace_id">{trace.trace_id ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="session_id">{trace.session_id ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="steps">{trace.steps || "—"}</Descriptions.Item>
              <Descriptions.Item label="stop_reason">{trace.stop_reason || "—"}</Descriptions.Item>
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
