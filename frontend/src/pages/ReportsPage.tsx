import { useRef, useState } from "react";
import { Button, Card, Space, Typography, message } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { api, downloadMarkdown, type ChatSession, type EvalArm, type Fact } from "../api";

const { Paragraph, Text } = Typography;

const FETCH_LIMIT = 1000; // 与后端 le=1000 一致

/** 报告中心：选择数据源，一键导出 Markdown。 */
export default function ReportsPage() {
  const [busy, setBusy] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);  // X6：批次进度
  const abortRef = useRef(false);  // X6：取消导出

  const exportMemory = async () => {
    setBusy("memory");
    try {
      const facts: Fact[] = await api.facts(FETCH_LIMIT);
      const truncated = facts.length >= FETCH_LIMIT;
      const lines = [
        `# Anchorline 记忆报告`,
        "",
        `- 导出时间：${new Date().toLocaleString()}`,
        `- 事实数：${facts.length}${truncated ? "（达到后端上限，可能截断）" : ""}`,
        "",
      ];
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
      message.success(`记忆报告已导出（${facts.length} 条${truncated ? "，达到上限可能截断" : ""}）`);
    } catch (e) {
      message.error(`记忆报告导出失败：${String(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const exportSessions = async () => {
    setBusy("sessions");
    abortRef.current = false;
    try {
      const sessions: ChatSession[] = await api.listSessions(FETCH_LIMIT);
      const truncated = sessions.length >= FETCH_LIMIT;
      // Y1：分批并发（10 个/批）+ allSettled —— 单个会话失败不导致整份报告归零
      const BATCH = 10;
      const msgsList: (Awaited<ReturnType<typeof api.sessionMessages>> | null)[] = new Array(sessions.length).fill(null);
      const failed: string[] = [];
      for (let i = 0; i < sessions.length; i += BATCH) {
        if (abortRef.current) {
          message.info("已取消导出（未写入文件）");
          return;
        }
        setProgress(`正在拉取会话消息：${Math.min(i + BATCH, sessions.length)}/${sessions.length}`);
        const batch = sessions.slice(i, i + BATCH);
        const settled = await Promise.allSettled(batch.map((s) => api.sessionMessages(s.id)));
        settled.forEach((r, j) => {
          if (r.status === "fulfilled") {
            msgsList[i + j] = r.value;
          } else {
            failed.push(batch[j].title);
          }
        });
      }
      const lines = [
        `# Anchorline 会话报告`,
        "",
        `- 导出时间：${new Date().toLocaleString()}`,
        `- 会话数：${sessions.length}${truncated ? "（达到后端上限，可能截断）" : ""}`,
        failed.length ? `- **${failed.length} 个会话消息加载失败**（仅列出会话标题）：${failed.slice(0, 10).join("、")}` : "",
        "",
      ].filter(Boolean);
      sessions.forEach((s, i) => {
        const msgs = msgsList[i];
        lines.push(`## ${s.title}（${s.id.slice(0, 8)}）`, "");
        if (msgs === null) {
          lines.push(`- 主题：${s.topic ?? "—"} ｜ 创建：${new Date(s.created_at).toLocaleString()} ｜ **消息拉取失败**`, "");
          return;
        }
        lines.push(`- 主题：${s.topic ?? "—"} ｜ 创建：${new Date(s.created_at).toLocaleString()} ｜ 消息：${msgs.length}`, "");
        for (const m of msgs) {
          lines.push(`### ${m.role === "user" ? "我" : "Anchorline"}  ${new Date(m.created_at).toLocaleString()}`, "", m.content, "");
        }
      });
      downloadMarkdown(`anchorline-sessions-report-${Date.now()}.md`, lines.join("\n"));
      message.success(`会话报告已导出（${sessions.length} 个${truncated ? "，达到上限可能截断" : ""}）`);
    } catch (e) {
      message.error(`会话报告导出失败：${String(e)}`);
    } finally {
      setBusy(null);
      setProgress(null);
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
    } catch (e) {
      message.error(`评测报告导出失败：${String(e)}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card title="报告中心">
      <Paragraph type="secondary">
        选择数据源生成 Markdown 报告（浏览器直接下载）。适合做周报、演示材料和交付记录。
        <br />
        注意：事实与会话列表由后端分页接口返回，最多 <Text code>{FETCH_LIMIT}</Text> 条；导出文件头部会标明是否达到上限（可能截断）。
      </Paragraph>
      <Space wrap>
        <Button icon={<DownloadOutlined />} loading={busy === "memory"} onClick={() => void exportMemory()}>
          记忆报告（最多 {FETCH_LIMIT} 条事实）
        </Button>
        <Button icon={<DownloadOutlined />} loading={busy === "sessions"} onClick={() => void exportSessions()}>
          会话报告（最多 {FETCH_LIMIT} 个会话）
        </Button>
        {busy === "sessions" && (
          <Button danger onClick={() => { abortRef.current = true; }}>
            取消
          </Button>
        )}
        <Button icon={<DownloadOutlined />} loading={busy === "eval"} onClick={() => void exportEval()}>
          评测报告（臂对比）
        </Button>
      </Space>
      {progress && (
        <Paragraph type="secondary" style={{ marginTop: 8 }}>
          <Text>{progress}</Text>
        </Paragraph>
      )}
      <Paragraph type="secondary" style={{ marginTop: 12 }}>
        <Text>提示</Text>：会话报告会并发拉取每个会话的消息（10 个/批），进度显示在按钮下方；导出中可点「取消」（不会写入文件）。
      </Paragraph>
    </Card>
  );
}
