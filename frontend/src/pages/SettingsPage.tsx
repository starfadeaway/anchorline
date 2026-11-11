import { useEffect, useState } from "react";
import { Alert, Button, Card, ColorPicker, Descriptions, Divider, Input, Segmented, Space, Switch, Tag, Typography, message } from "antd";
import { api, type SettingsOut, type SkillInfo } from "../api";

const { Paragraph, Text } = Typography;

const THEME_KEY = "anchorline-theme";
const THEMES: { name: string; neon: string; neon2: string }[] = [
  { name: "青（默认）", neon: "#00d4ff", neon2: "#7c5cff" },
  { name: "紫", neon: "#a78bfa", neon2: "#f472b6" },
  { name: "绿", neon: "#4ade80", neon2: "#22d3ee" },
  { name: "橙", neon: "#fb923c", neon2: "#f43f5e" },
];

export function applyTheme(neon: string, neon2: string): void {
  // X24：light 模式由 styles.css 的浅色变量负责（内联覆盖会导致浅底亮字）；dark 才写内联
  const light = document.documentElement.dataset.theme === "light";
  if (light) {
    document.documentElement.style.removeProperty("--neon");
    document.documentElement.style.removeProperty("--neon-2");
  } else {
    document.documentElement.style.setProperty("--neon", neon);
    document.documentElement.style.setProperty("--neon-2", neon2);
  }
}

/** 设置页：运行配置（只读）+ 主题色切换（本地保存）。 */
export default function SettingsPage() {
  const [s, setS] = useState<SettingsOut | null>(null);
  const [err, setErr] = useState("");
  const [color, setColor] = useState<string>(() => localStorage.getItem(THEME_KEY) || "#00d4ff");
  const [mode, setMode] = useState<string>(() => localStorage.getItem("anchorline-mode") || "dark");
  const [apiToken, setApiToken] = useState<string>(() => localStorage.getItem("anchorline-token") || "");
  const [skills, setSkills] = useState<SkillInfo[]>([]);

  const load = () => {
    api
      .settings()
      .then((v) => {
        setS(v);
        setErr("");
      })
      .catch((e) => setErr(String(e)));
    api.listSkills().then(setSkills).catch(() => setSkills([]));
  };
  useEffect(load, []);

  const pick = (neon: string, neon2: string) => {
    setColor(neon);
    localStorage.setItem(THEME_KEY, neon);
    // X23：副色也保存，避免只记住主色
    localStorage.setItem("anchorline-theme2", neon2);
    applyTheme(neon, neon2);
    window.dispatchEvent(new Event("anchorline-theme-changed"));
    message.success("主题色已应用");
  };

  const restore = () => {
    localStorage.removeItem(THEME_KEY);
    localStorage.removeItem("anchorline-theme2");
    applyTheme("#00d4ff", "#7c5cff");
    window.dispatchEvent(new Event("anchorline-theme-changed"));
    setColor("#00d4ff");
    message.success("已恢复默认主题");
  };

  return (
    <Card title="设置 / 运行配置（只读）" extra={<Button onClick={load}>重新检查</Button>}>
      <Paragraph type="secondary">
        密钥只在本地 <Text code>.env</Text>，前端与接口都不返回 key；这里只展示模型名与预算。
      </Paragraph>
      {err && <Alert type="error" showIcon message="配置加载失败" description={err} style={{ marginBottom: 12 }} />}
      {s && (
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="版本">{s.version}</Descriptions.Item>
          <Descriptions.Item label="数据库">{s.db_ok ? <Tag color="green">ok</Tag> : <Tag color="red">不可用</Tag>}</Descriptions.Item>
          <Descriptions.Item label="向量索引">{s.index_ready ? <Tag color="green">就绪</Tag> : <Tag color="orange">未建索引（检索退回 BM25）</Tag>}</Descriptions.Item>
          <Descriptions.Item label="reader">{s.reader_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="judge">{s.judge_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="embedding">{s.embedding_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="rerank">{s.rerank_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="MiniMax（聊天可选）">{s.minimax_model || "—"}（{s.minimax_base_url || "—"}）</Descriptions.Item>
          <Descriptions.Item label="聊天可切换"><Space>{s.chat_models.map((m) => <Tag key={m}>{m}</Tag>)}</Space></Descriptions.Item>
          <Descriptions.Item label="预算档"><Space>{s.budgets.map((b) => <Tag key={b}>{b}</Tag>)}</Space></Descriptions.Item>
        </Descriptions>
      )}

      <Divider titlePlacement="start">技能（可开关）</Divider>
      <Paragraph type="secondary">
        内置技能是**提示模块**：开启后聊天时把该技能指令拼进 system prompt；不引入外部工具、不越过记忆边界。
      </Paragraph>
      {skills.length === 0 ? (
        <Text type="secondary">加载中…</Text>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }}>
          {skills.map((sk) => (
            <div key={sk.name} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Switch
                checked={sk.enabled}
                onChange={(v) =>
                  api
                    .toggleSkill(sk.name, v)
                    .then(() => {
                      setSkills((prev) => prev.map((x) => (x.name === sk.name ? { ...x, enabled: v } : x)));
                      message.success(`${sk.title} 已${v ? "开启" : "关闭"}`);
                    })
                    .catch((e) => message.error(`技能切换失败：${String(e)}`))
                }
              />
              <Text strong style={{ minWidth: 96 }}>{sk.title}</Text>
              <Text type="secondary">{sk.description}</Text>
            </div>
          ))}
        </Space>
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
            window.dispatchEvent(new Event("anchorline-theme-changed"));
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

