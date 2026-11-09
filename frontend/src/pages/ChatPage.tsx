import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Card, Collapse, Descriptions, Empty, Input, List, message, Segmented, Space, Tooltip, Typography } from "antd";
import { DownloadOutlined, PlusOutlined } from "@ant-design/icons";
import { api, downloadMarkdown, type ChatResp, type ChatSession, type Msg, type SettingsOut, type TraceRow } from "../api";

const { Text } = Typography;

/** 按对话内容（主题）分组，而不是按时间；topic 由模型生成，这里只是兜底规则。 */
function topicOf(title: string): string {
  const t = title.toLowerCase();
  if (/游泳|泳池|自由泳|蛙泳|蝶泳|仰泳|swim/.test(t)) return "游泳记录";
  if (/乒乓球|羽毛球|网球|篮球|足球|排球|台球/.test(t)) return "球类运动";
  if (/5k|跑步|配速|跑|pb|半马|全马/.test(t)) return "跑步记录";
  if (/健身|骑行|瑜伽|力量|增肌/.test(t)) return "健身记录";
  if (/模型|你是谁|介绍一下|deepseek|minimax/.test(t)) return "模型与身份";
  if (/记住|记忆|存下|保存/.test(t)) return "记忆写入";
  if (/你好|hi|hello|聊天/.test(t)) return "闲聊";
  return "其他对话";
}

function groupByTopic(sessions: ChatSession[]): [string, ChatSession[]][] {
  const m = new Map<string, ChatSession[]>();
  for (const s of sessions) {
    // 优先用模型生成的主题（s.topic），回退关键词规则
    const k = (s.topic && s.topic.trim()) || topicOf(s.title);
    m.set(k, [...(m.get(k) ?? []), s]);
  }
  return [...m.entries()];
}

function parseToolCalls(raw: string | null): { name: string; arguments: string }[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw) as { name?: string; arguments?: unknown }[];
    if (!Array.isArray(arr)) return [];
    return arr.map((x) => ({
      name: String(x.name ?? ""),
      arguments: typeof x.arguments === "string" ? x.arguments : JSON.stringify(x.arguments ?? {}),
    }));
  } catch {
    return [];
  }
}

/** 聊天页：左会话（主题分组）+ 中聊天（含指标条）+ 右 Trace；底部显示运行环境。 */
export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState("deepseek");
  const [trace, setTrace] = useState<ChatResp | null>(null);
  const [env, setEnv] = useState<SettingsOut | null>(null);
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
    api.settings().then(setEnv).catch(() => setEnv(null));
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const grouped = useMemo(() => groupByTopic(sessions), [sessions]);

  const fromTraceRow = (row: TraceRow, sessionId: string): ChatResp => ({
    answer: "",
    stop_reason: row.resolution ?? "",
    steps: row.steps ?? 0,
    tool_calls: parseToolCalls(row.injected_fact_ids),
    trace_id: row.id,
    session_id: sessionId,
    meta: { duration_ms: null, total_tokens: row.used_tokens, tool_errors: 0, run_id: String(row.id) },
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
      lines.push("## Trace", "", `- run_id：${trace.trace_id ?? "—"}`, `- 模型：${trace.meta?.model ?? model}`, `- 步数：${trace.steps || "—"}`, `- 工具：${trace.tool_calls.length}`, `- 失败：${trace.meta?.tool_errors ?? 0}`, `- 耗时：${trace.meta?.duration_ms ?? "—"} ms`, `- Token：${trace.meta?.total_tokens ?? "—"}`, `- 终止：${trace.stop_reason || "—"}`, "");
      lines.push("| 工具 | 参数 |", "|---|---|");
      for (const t of trace.tool_calls) lines.push(`| ${t.name} | \`${t.arguments.replace(/\|/g, "/")}\` |`);
    }
    downloadMarkdown(`anchorline-${(active ?? "new").slice(0, 8)}-${Date.now()}.md`, lines.join("\n"));
    message.success("已导出 Markdown");
  };

  return (
    <div className="chat-layout">
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
            <Collapse
              size="small"
              ghost
              defaultActiveKey={grouped.map(([t]) => t)}
              items={grouped.map(([topic, rows]) => ({
                key: topic,
                label: <span className="session-group-title">{topic} · {rows.length}</span>,
                children: (
                  <List
                    size="small"
                    dataSource={rows}
                    renderItem={(s) => (
                      <List.Item className={`session-item ${active === s.id ? "active" : ""}`} onClick={() => void loadSession(s.id)}>
                        <div>
                          <div className="session-title">{s.title}</div>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {new Date(s.created_at).toLocaleString()} · {s.message_count} 条
                          </Text>
                        </div>
                      </List.Item>
                    )}
                  />
                ),
              }))}
            />
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
          <div className="messages" key={active ?? "new"}>
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
            {trace && (
              <div className="metrics-bar">
                <span>模型 <b>{trace.meta?.model ?? model}</b></span>
                <span>步数 <b>{trace.steps > 0 ? trace.steps : "—"}</b></span>
                <span>工具 <b>{trace.tool_calls.length}</b></span>
                <span>失败 <b>{trace.meta?.tool_errors ?? 0}</b></span>
                <span>耗时 <b>{trace.meta?.duration_ms ?? "—"} ms</b></span>
                <span>Token <b>{trace.meta?.total_tokens ?? "—"}</b></span>
                <span>终止 <b>{trace.stop_reason || "—"}</b></span>
                <span>Run <b>{trace.trace_id ?? "—"}</b></span>
              </div>
            )}
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

        <Card title="Trace" size="small" className="chat-col" extra={active ? <Text type="secondary" style={{ fontSize: 11 }}>按会话保存</Text> : null}>
          {!trace ? (
            <Empty description="发送消息后显示本轮 trace" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <>
              <Descriptions size="small" column={1} bordered>
                <Descriptions.Item label="run_id">{trace.trace_id ?? "—"}</Descriptions.Item>
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

      <div className="env-bar">
        <span><span className={`dot ${env?.db_ok ? "ok" : "bad"}`} /><em>索引</em> <b>{env?.db_ok ? "就绪" : "—"}</b></span>
        <span><span className={`dot ${env ? "ok" : "bad"}`} /><em>Embedding</em> <b>{env?.embedding_model ?? "—"}</b></span>
        <span><span className={`dot ${env ? "ok" : "bad"}`} /><em>Rerank</em> <b>{env?.rerank_model ?? "—"}</b></span>
        <span><span className={`dot ${env?.db_ok ? "ok" : "bad"}`} /><em>MySQL</em> <b>{env?.db_ok ? "已连接" : "未连接"}</b></span>
        <span><span className={`dot ${env ? "ok" : "bad"}`} /><em>Reader</em> <b>{env?.reader_model ?? "—"}</b></span>
        <span><span className={`dot ${env ? "ok" : "bad"}`} /><em>Judge</em> <b>{env?.judge_model ?? "—"}</b></span>
        <span><span className="dot ok" /><em>预算</em> <b>{env?.budgets?.join(" / ") ?? "—"}</b></span>
      </div>
    </div>
  );
}
