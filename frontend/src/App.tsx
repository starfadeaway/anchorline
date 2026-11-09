import { Layout, Menu, Typography } from "antd";
import { CommentOutlined, DatabaseOutlined, ExperimentOutlined, SettingOutlined } from "@ant-design/icons";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import MemoryPage from "./pages/MemoryPage";
import EvalPage from "./pages/EvalPage";
import SettingsPage from "./pages/SettingsPage";

const { Sider, Content, Header } = Layout;
const { Text } = Typography;

const items = [
  { key: "/chat", icon: <CommentOutlined />, label: <Link to="/chat">聊天</Link> },
  { key: "/memory", icon: <DatabaseOutlined />, label: <Link to="/memory">记忆</Link> },
  { key: "/eval", icon: <ExperimentOutlined />, label: <Link to="/eval">评测</Link> },
  { key: "/settings", icon: <SettingOutlined />, label: <Link to="/settings">设置</Link> },
];

export default function App() {
  const loc = useLocation();
  const selected = items.find((i) => loc.pathname.startsWith(i.key))?.key ?? "/chat";

  return (
    <Layout className="app-layout">
      <Header className="app-header">
        <Text strong className="brand">Anchorline</Text>
        <Text type="secondary">预算内记忆层 · V2-web 主评测 / V1-KU 冲突专项</Text>
      </Header>
      <Layout>
        <Sider width={168} className="app-sider">
          <Menu mode="inline" selectedKeys={[selected]} items={items} />
        </Sider>
        <Content className="app-content">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/memory" element={<MemoryPage />} />
            <Route path="/eval" element={<EvalPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
