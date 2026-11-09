// React 19 兼容补丁：必须在 antd 之前引入
import "@ant-design/v5-patch-for-react-19";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import ErrorBoundary from "./ErrorBoundary";
import "antd/dist/reset.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.darkAlgorithm,
          token: {
            // 科技风：霓虹青主色、深空底、紧凑圆角；不改字体
            colorPrimary: "#00d4ff",
            colorInfo: "#00d4ff",
            colorBgBase: "#070b12",
            colorBgContainer: "#0d1420",
            colorBorder: "#1d2b3f",
            borderRadius: 6,
            controlHeight: 32,
          },
        }}
      >
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ConfigProvider>
    </ErrorBoundary>
  </StrictMode>,
);
