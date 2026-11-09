import { useEffect } from "react";
import { Layout, Menu, Typography, message } from "antd";
import { CommentOutlined, DatabaseOutlined, ExperimentOutlined, FileTextOutlined, DashboardOutlined, SettingOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import MemoryPage from "./pages/MemoryPage";
import EvalPage from "./pages/EvalPage";
import SessionsPage from "./pages/SessionsPage";
import ReviewPage from "./pages/ReviewPage";
import ReportsPage from "./pages/ReportsPage";
import MonitorPage from "./pages/MonitorPage";
import SettingsPage from "./pages/SettingsPage";

const { Sider, Content, Header } = Layout;
const { Text } = Typography;

// 菜单 7 项；对比/Trace 并入评测页 Tabs，会话管理从聊天页「管理」进入
const items = [
  { key: "/chat", icon: <CommentOutlined />, label: <Link to="/chat">聊天</Link> },
  { key: "/memory", icon: <DatabaseOutlined />, label: <Link to="/memory">记忆</Link> },
  { key: "/eval", icon: <ExperimentOutlined />, label: <Link to="/eval">评测</Link> },
  { key: "/review", icon: <SafetyCertificateOutlined />, label: <Link to="/review">审核</Link> },
  { key: "/reports", icon: <FileTextOutlined />, label: <Link to="/reports">报告</Link> },
  { key: "/monitor", icon: <DashboardOutlined />, label: <Link to="/monitor">监控</Link> },
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
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/monitor" element={<MonitorPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
