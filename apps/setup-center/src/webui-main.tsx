// ─── SeeAgent WebUI 独立入口 ───
// 这是一个完全独立的 Web 应用，不依赖 OpenAkita 的主应用

import React from "react";
import ReactDOM from "react-dom/client";
import "./i18n";  // 加载 i18n 配置
import { WebUIView } from "./views/WebUIView";
import "./styles.css";

// 独立的 WebUI 应用
function WebUIApp() {
  return (
    <div className="h-screen w-screen overflow-hidden">
      <WebUIView />
    </div>
  );
}

// 渲染应用
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WebUIApp />
  </React.StrictMode>
);
