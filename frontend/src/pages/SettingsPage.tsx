import { useEffect, useState } from "react";
import { Button, Card, Descriptions, Space, Tag, Typography, message } from "antd";
import { api, type SettingsOut } from "../api";

const { Paragraph, Text } = Typography;

/** 设置页：只读展示运行配置（不含任何密钥）与健康状态。 */
export default function SettingsPage() {
  const [s, setS] = useState<SettingsOut | null>(null);
  const [err, setErr] = useState("");

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

  return (
    <Card
      title="设置 / 运行配置"
      extra={<Button onClick={load}>重新检查</Button>}
    >
      <Paragraph type="secondary">
        密钥只在本地 <Text code>.env</Text>，前端与接口都不返回 key；这里只展示模型名与预算。
      </Paragraph>
      {err && <Paragraph type="danger">{err}</Paragraph>}
      {s && (
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="版本">{s.version}</Descriptions.Item>
          <Descriptions.Item label="数据库">
            {s.db_ok ? <Tag color="green">ok</Tag> : <Tag color="red">不可用</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="reader">{s.reader_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="judge">{s.judge_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="embedding">{s.embedding_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="rerank">{s.rerank_model || "—"}</Descriptions.Item>
          <Descriptions.Item label="预算档">
            <Space>{s.budgets.map((b) => <Tag key={b}>{b}</Tag>)}</Space>
          </Descriptions.Item>
        </Descriptions>
      )}
      <Paragraph type="secondary" style={{ marginTop: 12 }}>
        评测模式固定 reader / embedding / judge；模型切换只用于聊天模式。
      </Paragraph>
      <Space />
    </Card>
  );
}
