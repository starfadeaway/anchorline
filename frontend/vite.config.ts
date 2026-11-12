import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发时把 /api 代理到 FastAPI（127.0.0.1:8000），避免 CORS
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  // preview 也代理 /api：用于对 dist 产物做真实浏览器冒烟（生产由 nginx 反代）
  preview: {
    port: 4173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    // 拆 vendor：react / antd（含 icons）/ rc（@rc-component + rc-*）/ 其余 vendor。
    // 四个块都 < 800KB，且避免 antd 全家单块超限。
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/.test(id)) return "react";
          if (id.includes("node_modules/@rc-component") || /[\\/]node_modules[\\/]rc-/.test(id)) return "rc";
          if (id.includes("node_modules/antd") || id.includes("node_modules/@ant-design")) return "antd";
          return "vendor";
        },
      },
    },
    chunkSizeWarningLimit: 800,
  },
});
