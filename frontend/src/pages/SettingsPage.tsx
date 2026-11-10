import { useEffect, useState } from "react";
import { Alert, Button, Card, ColorPicker, Descriptions, Divider, Input, Segmented, Space, Tag, Typography, message } from "antd";
import { api, type SettingsOut } from "../api";

const { Paragraph, Text } = Typography;

const THEME_KEY = "anchorline-theme";
const THEMES: { name: string; neon: string; neon2: string }[] = [
  { name: "青（默认）", neon: "#00d4ff", neon2: "#7c5cff" },
  { name: "紫", neon: "#a78bfa", neon2: "#f472b6" },
  { name: "绿", neon: "#4ade80", neon2: "#22d3ee" },
  { name: "橙", neon: "#fb923c", neon2: "#f43f5e" },
];

export function applyTheme(neon: string, neon2: string): void {
  document.documentElement.style.setProperty("--neon", neon);
  document.documentElement.style.setProperty("--neon-2", neon2);
}

/** 设置页：运行配置（只读）+ 主题色切换（本地保存）。 */
export default function SettingsPage() {
  const [s, setS] = useState<SettingsOut | null>(null);
  const [err, setErr] = useState("");
  const [color, setColor] = useState<string>(() => localStorage.getItem(THEME_KEY) || "#00d4ff");
  const [mode, setMode] = useState<string>(() => localStorage.getItem("anchorline-mode") || "dark");
  const [apiToken, setApiToken] = useState<string>(() => localStorage.getItem("anchorline-token") || "");

  const load = () => {
    api
      .settings()
      .then((v) => {
        setS(v);
        setErr("");
      })
      .catch((e) => setErr(String(e)));
  };
  useEffect(load, []);

  const pick = (neon: string, neon2: string) => {
    setColor(neon);
    localStorage.setItem(THEME_KEY, neon);
    applyTheme(neon, neon2);
    message.success("主题色已应用");
  };

  const restore = () => {
    localStorage.removeItem(THEME_KEY);
    applyTheme("#00d4ff", "#7c5cff");
    setColor("#00d4ff");
    message.success("已恢复默认主题");
  };

  return (
    <Card title="设置 / 运行配置" extra={<Button onClick={load}>重新检查</Button>}>
      <Paragraph type="secondary">
        密钥只在本地 <Text code>.env</Text>，前端与接口都不返回 key；这里只展示模型名与预算。
      </Paragraph>
      {err && <Alert type="error" showIcon message="配置加载失败" description={err} style={{ marginBottom: 12 }} />}
      {s && (
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="版本">{s.version}</Descriptions.Item>
          <Descriptions.Item label="数据库">{s.db_ok ? <Tag color="green">ok</Tag> : <Tag color="red">不可用</Tag>}</Descriptions.Item>
          <Descriptions.Item label="reader">{s.reader_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="judge">{s.judge_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="embedding">{s.embedding_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="rerank">{s.rerank_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="MiniMax（聊天可选）">{s.minimax_model || "—"}（{s.minimax_base_url || "—"}）</Descriptions.Item>
          <Descriptions.Item label="聊天可切换"><Space>{s.chat_models.map((m) => <Tag key={m}>{m}</Tag>)}</Space></Descriptions.Item>
          <Descriptions.Item label="预算档"><Space>{s.budgets.map((b) => <Tag key={b}>{b}</Tag>)}</Space></Descriptions.Item>
        </Descriptions>
      )}

      <Divider titlePlacement="start">外观</Divider>
      <Space wrap style={{ marginBottom: 12 }}>
        <Text type="secondary">模式</Text>
        <Segmented
          value={mode}
          onChange={(v) => {
            const m = String(v);
            setMode(m);
            localStorage.setItem("anchorline-mode", m);
            window.location.reload();
          }}
          options={[
            { label: "夜间", value: "dark" },
            { label: "日间", value: "light" },
          ]}
        />
      </Space>
      <div />
      <Space wrap>
        {THEMES.map((t) => (
          <Button key={t.name} onClick={() => pick(t.neon, t.neon2)} style={{ borderColor: t.neon, color: t.neon }}>
            {t.name}
          </Button>
        ))}
        <ColorPicker value={color} onChangeComplete={(c) => pick(c.toHexString(), "#7c5cff")} showText />
        <Button onClick={restore}>恢复默认</Button>
      </Space>
      <Paragraph type="secondary" style={{ marginTop: 12 }}>
        主题色保存在浏览器 localStorage，只影响本机界面，不写入后端。
      </Paragraph>

      <Divider titlePlacement="start">评测说明</Divider>
      <Paragraph type="secondary">
        评测模式固定 reader / embedding / judge；模型切换只用于聊天模式。
      </Paragraph>

      <Divider titlePlacement="start">API Token（可选）</Divider>
      <Paragraph type="secondary">
        后端在 <Text code>.env</Text> 设置 <Text code>API_TOKEN</Text> 后启用鉴权；这里填写的 token 只存本地 localStorage。
      </Paragraph>
      <Space wrap>
        <Input.Password
          placeholder="X-API-Token"
          value={apiToken}
          onChange={(e) => setApiToken(e.target.value)}
          style={{ width: 280 }}
        />
        <Button
          type="primary"
          onClick={() => {
            localStorage.setItem("anchorline-token", apiToken.trim());
            message.success("Token 已保存（刷新后生效）");
          }}
        >
          保存
        </Button>
        <Button
          onClick={() => {
            localStorage.removeItem("anchorline-token");
            setApiToken("");
            message.success("已清除 Token");
          }}
        >
          清除
        </Button>
      </Space>
    </Card>
  );
}

