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
  build: {
    // 拆 vendor，避免单个 chunk 过大（antd 单独成块，业务代码按路由懒加载）
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          antd: ["antd", "@ant-design/icons"],
        },
      },
    },
    chunkSizeWarningLimit: 1500,
  },
});
