import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import ErrorBoundary from "./ErrorBoundary";
import "antd/dist/reset.css";
import "./styles.css";

// 注意：不包 StrictMode —— antd 部分组件的 effect cleanup 在 StrictMode 双调用下会报
// "destroy is not a function"（开发期问题），生产构建无此行为。
const light = typeof localStorage !== "undefined" && localStorage.getItem("anchorline-mode") === "light";

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: light ? theme.defaultAlgorithm : theme.darkAlgorithm,
        token: light
          ? {
              colorPrimary: "#0b8fd6",
              colorInfo: "#0b8fd6",
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
              colorPrimary: "#00d4ff",
              colorInfo: "#00d4ff",
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
  </ErrorBoundary>,
);

