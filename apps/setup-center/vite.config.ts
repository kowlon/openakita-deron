import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 唯一数据源: Python 后端的 providers.json
      // 前端通过此 alias 直接 import，与后端共享同一份文件
      // 新增服务商只需修改 providers.json，前后端自动同步
      "@shared/providers.json": path.resolve(
        __dirname,
        "../../src/openakita/llm/registries/providers.json",
      ),
    },
  },
  // 多入口支持：主应用和独立 WebUI
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, "index.html"),
        webui: path.resolve(__dirname, "webui.html"),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
  clearScreen: false,
});

