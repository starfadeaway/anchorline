import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import ErrorBoundary from "./ErrorBoundary";
import "antd/dist/reset.css";
import "./styles.css";

const THEME_KEY = "anchorline-theme";
const MODE_KEY = "anchorline-mode";
const DARK_NEON = "#00d4ff";
const LIGHT_NEON = "#0b8fd6";

function readNeon(): string {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) return saved;
  return localStorage.getItem(MODE_KEY) === "light" ? LIGHT_NEON : DARK_NEON;
}

/** 主题色 / 日夜切换不整页刷新：SettingsPage 只 dispatch 事件，这里重渲染 ConfigProvider。 */
function AppRoot() {
  const [neon, setNeon] = useState<string>(readNeon);
  const [mode, setMode] = useState<string>(() => localStorage.getItem(MODE_KEY) || "dark");

  useEffect(() => {
    const onChange = () => {
      setNeon(readNeon());
      setMode(localStorage.getItem(MODE_KEY) || "dark");
      const neon2 = localStorage.getItem("anchorline-theme2");
      if (neon2 && document.documentElement.dataset.theme !== "light") {
        document.documentElement.style.setProperty("--neon-2", neon2);
      }
    };
    window.addEventListener("anchorline-theme-changed", onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener("anchorline-theme-changed", onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  const light = mode === "light";
  const primary = light && !localStorage.getItem(THEME_KEY) ? LIGHT_NEON : neon;

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: light ? theme.defaultAlgorithm : theme.darkAlgorithm,
        token: light
          ? {
              colorPrimary: primary,
              colorInfo: primary,
              colorBgBase: "#f4f7fb",
              colorBgContainer: "#ffffff",
              colorBgElevated: "#ffffff",
              colorBorder: "#dbe3ef",
              colorBorderSecondary: "#e6ecf5",
              colorText: "#18202e",
              colorTextSecondary: "#46556d",
              colorTextTertiary: "#5c6e88",
              colorTextQuaternary: "#7b8ba3",
              borderRadius: 6,
              controlHeight: 32,
            }
          : {
              colorPrimary: primary,
              colorInfo: primary,
              colorBgBase: "#070b12",
              colorBgContainer: "#0d1420",
              colorBgElevated: "#111a28",
              colorBorder: "#1d2b3f",
              colorBorderSecondary: "#26374d",
              // 文字层级：保证在 #0d1420 背景上对比度 >= 4.5:1（WCAG AA）
              colorText: "#e6edf7",
              colorTextSecondary: "#a8b8d0",
              colorTextTertiary: "#8195b0",
              colorTextQuaternary: "#6f829e",
              borderRadius: 6,
              controlHeight: 32,
            },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  // 不包 StrictMode：React 19 dev 下的双调用会让记忆页（10 组 Collapse + 40 行表格 +
  // 50 个时间节点）在切页时明显卡顿；生产构建无此问题，dev 自检让位于可用性。
  <ErrorBoundary>
    <AppRoot />
  </ErrorBoundary>,
);
