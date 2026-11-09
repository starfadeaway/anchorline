import { useState } from "react";
import { Button, Card, Space, Typography, message } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { api, downloadMarkdown, type ChatSession, type EvalArm, type Fact } from "../api";

const { Paragraph, Text } = Typography;

/** 报告中心：选择数据源，一键导出 Markdown。 */
export default function ReportsPage() {
  const [busy, setBusy] = useState<string | null>(null);

  const exportMemory = async () => {
    setBusy("memory");
    try {
      const facts: Fact[] = await api.facts();
      const lines = [`# Anchorline 记忆报告`, "", `- 导出时间：${new Date().toLocaleString()}`, `- 事实总数：${facts.length}`, ""];
      const byEntity = new Map<string, Fact[]>();
      for (const f of facts) byEntity.set(f.entity_id, [...(byEntity.get(f.entity_id) ?? []), f]);
      for (const [entity, rows] of byEntity) {
        lines.push(`## ${entity}`, "");
        for (const f of rows) {
          lines.push(`- **${f.attribute}** = ${f.value} ｜ ${f.valid_to ? "已失效" : "当前"} ｜ 生效 ${new Date(f.valid_from).toLocaleString()}`);
        }
        lines.push("");
      }
      downloadMarkdown(`anchorline-memory-report-${Date.now()}.md`, lines.join("\n"));
      message.success("记忆报告已导出");
    } finally {
      setBusy(null);
    }
  };

  const exportSessions = async () => {
    setBusy("sessions");
    try {
      const sessions: ChatSession[] = await api.listSessions();
      const lines = [`# Anchorline 会话报告`, "", `- 导出时间：${new Date().toLocaleString()}`, `- 会话数：${sessions.length}`, ""];
      for (const s of sessions) {
        const msgs = await api.sessionMessages(s.id);
        lines.push(`## ${s.title}（${s.id.slice(0, 8)}）`, "");
        lines.push(`- 主题：${s.topic ?? "—"} ｜ 创建：${new Date(s.created_at).toLocaleString()} ｜ 消息：${msgs.length}`, "");
        for (const m of msgs) {
          lines.push(`### ${m.role === "user" ? "我" : "Anchorline"}  ${new Date(m.created_at).toLocaleString()}`, "", m.content, "");
        }
      }
      downloadMarkdown(`anchorline-sessions-report-${Date.now()}.md`, lines.join("\n"));
      message.success("会话报告已导出");
    } finally {
      setBusy(null);
    }
  };

  const exportEval = async () => {
    setBusy("eval");
    try {
      const arms: EvalArm[] = await api.evalSummary();
      const lines = [`# Anchorline 评测报告`, "", `- 导出时间：${new Date().toLocaleString()}`, "", "| 臂 | 准确率 | 题数 | 来源 | 备注 |", "|---|---|---|---|---|"];
      for (const a of arms) lines.push(`| ${a.arm} | ${(a.accuracy * 100).toFixed(1)}% | ${a.n} | ${a.source} | ${a.note ?? "—"} |`);
      lines.push("", "> 配置：reader deepseek-flash / embedding Qwen3-Embedding-8B / 官方判分 / 4k / top-6 / 1 次/题。");
      downloadMarkdown(`anchorline-eval-report-${Date.now()}.md`, lines.join("\n"));
      message.success("评测报告已导出");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card title="报告中心">
      <Paragraph type="secondary">
        选择数据源生成 Markdown 报告（浏览器直接下载）。适合做周报、演示材料和交付记录。
      </Paragraph>
      <Space wrap>
        <Button icon={<DownloadOutlined />} loading={busy === "memory"} onClick={() => void exportMemory()}>
          记忆报告（全部事实）
        </Button>
        <Button icon={<DownloadOutlined />} loading={busy === "sessions"} onClick={() => void exportSessions()}>
          会话报告（全部对话）
        </Button>
        <Button icon={<DownloadOutlined />} loading={busy === "eval"} onClick={() => void exportEval()}>
          评测报告（臂对比）
        </Button>
      </Space>
      <Paragraph type="secondary" style={{ marginTop: 12 }}>
        <Text>提示</Text>：会话报告会逐条拉取消息，会话很多时下载会慢一些。
      </Paragraph>
    </Card>
  );
}
