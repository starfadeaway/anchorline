import { useEffect } from "react";
import { Layout, Menu, Typography, message } from "antd";
import { CommentOutlined, DatabaseOutlined, ExperimentOutlined, FileSearchOutlined, BarChartOutlined, MessageOutlined, SettingOutlined } from "@ant-design/icons";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import MemoryPage from "./pages/MemoryPage";
import EvalPage from "./pages/EvalPage";
import TracesPage from "./pages/TracesPage";
import ComparePage from "./pages/ComparePage";
import SessionsPage from "./pages/SessionsPage";
import SettingsPage from "./pages/SettingsPage";

const { Sider, Content, Header } = Layout;
const { Text } = Typography;

const items = [
  { key: "/chat", icon: <CommentOutlined />, label: <Link to="/chat">聊天</Link> },
  { key: "/memory", icon: <DatabaseOutlined />, label: <Link to="/memory">记忆</Link> },
  { key: "/eval", icon: <ExperimentOutlined />, label: <Link to="/eval">评测</Link> },
  { key: "/traces", icon: <FileSearchOutlined />, label: <Link to="/traces">Trace</Link> },
  { key: "/compare", icon: <BarChartOutlined />, label: <Link to="/compare">对比</Link> },
  { key: "/sessions", icon: <MessageOutlined />, label: <Link to="/sessions">会话管理</Link> },
  { key: "/settings", icon: <SettingOutlined />, label: <Link to="/settings">设置</Link> },
];

export default function App() {
  const loc = useLocation();
  const selected = items.find((i) => loc.pathname.startsWith(i.key))?.key ?? "/chat";

  // 启动时应用本地保存的主题色与日夜模式
  useEffect(() => {
    const neon = localStorage.getItem("anchorline-theme");
    if (neon) document.documentElement.style.setProperty("--neon", neon);
    document.documentElement.dataset.theme = localStorage.getItem("anchorline-mode") ?? "dark";
  }, []);

  // 全局兜底：未捕获错误 / 未处理的 Promise 拒绝都弹窗提示，不让页面静默崩
  useEffect(() => {
    const onError = (e: ErrorEvent) => {
      console.error("[anchorline] window error:", e.error ?? e.message);
      message.error(e.message || "发生未捕获错误");
    };
    const onRejection = (e: PromiseRejectionEvent) => {
      const reason = e.reason as { message?: string } | string | undefined;
      const text = typeof reason === "string" ? reason : reason?.message ?? "异步操作失败";
      console.error("[anchorline] unhandled rejection:", e.reason);
      message.error(text);
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return (
    <Layout className="app-layout">
      <Header className="app-header">
        <Text strong className="brand">ANCHORLINE</Text>
        <span className="status-dot" />
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
            <Route path="/traces" element={<TracesPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
