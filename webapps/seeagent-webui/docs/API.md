# SeeAgent WebUI API 文档

## 目录

1. [概述](#概述)
2. [通用说明](#通用说明)
3. [聊天接口](#聊天接口)
   - [POST /api/chat](#post-apichat)
   - [POST /api/chat/answer](#post-apichatanswer)
   - [POST /api/chat/cancel](#post-apichatcancel)
   - [POST /api/chat/skip](#post-apichatskip)
   - [POST /api/chat/insert](#post-apichatinsert)
4. [健康检查接口](#健康检查接口)
   - [GET /api/health](#get-apihealth)
   - [POST /api/health/check](#post-apihealthcheck)
5. [配置接口](#配置接口)
   - [GET /api/config/workspace-info](#get-apiconfigworkspace-info)
   - [GET /api/config/env](#get-apiconfigenv)
   - [GET /api/config/endpoints](#get-apiconfigendpoints)
   - [POST /api/config/reload](#post-apiconfigreload)
   - [POST /api/config/restart](#post-apiconfigrestart)
   - [GET /api/config/skills](#get-apiconfigskills)
   - [GET /api/config/providers](#get-apiconfigproviders)
   - [GET /api/config/list-models](#get-apiconfiglist-models)
6. [技能接口](#技能接口)
   - [GET /api/skills](#get-apiskills)
   - [GET /api/skills/config](#get-apiskillsconfig)
   - [POST /api/skills/config](#post-apiskillsconfig)
   - [POST /api/skills/install](#post-apiskillsinstall)
   - [POST /api/skills/reload](#post-apiskillsreload)
   - [GET /api/skills/marketplace](#get-apiskillsmarketplace)
7. [文件接口](#文件接口)
   - [GET /api/files](#get-apifiles)
8. [上传接口](#上传接口)
   - [POST /api/upload](#post-apiupload)
   - [GET /api/uploads/{filename}](#get-apiuploadsfilename)
9. [日志接口](#日志接口)
   - [GET /api/logs/service](#get-apilogsservice)
10. [系统接口](#系统接口)
    - [GET /](#get-)
    - [POST /api/shutdown](#post-apishutdown)

---

## 概述

SeeAgent WebUI API 是基于 FastAPI 构建的 RESTful API，提供了聊天、配置管理、技能管理、文件操作等功能。

- **基础路径**: `/api`
- **数据格式**: JSON
- **流式响应**: Server-Sent Events (SSE)

---

## 通用说明

### 请求头

| 头字段 | 说明 |
|--------|------|
| `Content-Type` | `application/json` (POST/PUT 请求) |
| `Accept` | `text/event-stream` (SSE 流式请求) |

### 响应格式

**成功响应**:
```json
{
  "success": true,
  "data": { ... }
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "错误信息"
}
```

---

## 聊天接口

### POST /api/chat

与 AI Agent 进行对话，返回 SSE 流式响应。

**请求体**:
```json
{
  "message": "用户消息内容",
  "conversation_id": "会话ID（可选）",
  "endpoint": "自定义端点（可选）"
}
```

**SSE 事件类型**:

| 事件类型 | 说明 |
|----------|------|
| `iteration_start` | 迭代开始 |
| `thinking_start` | 思考开始 |
| `thinking_delta` | 思考内容增量 |
| `thinking_end` | 思考结束 |
| `tool_call_start` | 工具调用开始 |
| `tool_call_end` | 工具调用结束 |
| `text_delta` | 文本响应增量 |
| `done` | 完成 |
| `error` | 错误 |

**SSE 事件示例**:
```
data: {"type": "thinking_start"}
data: {"type": "thinking_delta", "content": "正在分析..."}
data: {"type": "tool_call_start", "tool": "web_search", "args": {"query": "..."}}
data: {"type": "tool_call_end", "tool": "web_search", "result": "..."}
data: {"type": "text_delta", "content": "根据搜索结果..."}
data: {"type": "done"}
```

---

### POST /api/chat/answer

回答用户确认问题。

**请求体**:
```json
{
  "conversation_id": "会话ID",
  "answer": "用户回答内容"
}
```

**响应**:
```json
{
  "success": true
}
```

---

### POST /api/chat/cancel

取消当前正在进行的对话。

**请求体**:
```json
{
  "conversation_id": "会话ID"
}
```

**响应**:
```json
{
  "success": true,
  "message": "已取消"
}
```

---

### POST /api/chat/skip

跳过当前步骤。

**请求体**:
```json
{
  "conversation_id": "会话ID"
}
```

**响应**:
```json
{
  "success": true
}
```

---

### POST /api/chat/insert

在当前对话中插入消息。

**请求体**:
```json
{
  "conversation_id": "会话ID",
  "message": "插入的消息内容"
}
```

**响应**:
```json
{
  "success": true
}
```

---

## 健康检查接口

### GET /api/health

检查服务健康状态。

**响应**:
```json
{
  "status": "healthy",
  "timestamp": 1708502400
}
```

---

### POST /api/health/check

执行深度健康检查。

**响应**:
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "llm": "ok"
  }
}
```

---

## 配置接口

### GET /api/config/workspace-info

获取工作空间信息。

**响应**:
```json
{
  "workspace_path": "/path/to/workspace",
  "name": "workspace-name",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### GET /api/config/env

获取环境变量配置。

**响应**:
```json
{
  "env": {
    "OPENAI_API_KEY": "sk-***",
    "MODEL_NAME": "gpt-4"
  }
}
```

---

### GET /api/config/endpoints

获取所有 LLM 端点配置。

**响应**:
```json
{
  "endpoints": [
    {
      "name": "default",
      "model": "gpt-4",
      "api_base": "https://api.openai.com/v1"
    }
  ]
}
```

---

### POST /api/config/reload

重新加载配置文件。

**响应**:
```json
{
  "success": true,
  "message": "配置已重新加载"
}
```

---

### POST /api/config/restart

重启服务。

**响应**:
```json
{
  "success": true,
  "message": "服务正在重启"
}
```

---

### GET /api/config/skills

获取技能配置。

**响应**:
```json
{
  "skills": [
    {
      "name": "web_search",
      "enabled": true,
      "description": "网络搜索技能"
    }
  ]
}
```

---

### GET /api/config/providers

获取可用的 LLM 提供商列表。

**响应**:
```json
{
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "models": ["gpt-4", "gpt-3.5-turbo"]
    },
    {
      "name": "anthropic",
      "display_name": "Anthropic",
      "models": ["claude-3-opus", "claude-3-sonnet"]
    }
  ]
}
```

---

### GET /api/config/list-models

列出指定提供商的可用模型。

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| provider | string | 否 | 提供商名称 |

**响应**:
```json
{
  "models": [
    {
      "id": "gpt-4",
      "name": "GPT-4",
      "provider": "openai"
    }
  ]
}
```

---

## 技能接口

### GET /api/skills

获取所有可用技能列表。

**响应**:
```json
{
  "skills": [
    {
      "id": "web_search",
      "name": "网络搜索",
      "description": "搜索互联网获取信息",
      "enabled": true,
      "version": "1.0.0"
    }
  ]
}
```

---

### GET /api/skills/config

获取指定技能的配置。

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skill_id | string | 是 | 技能ID |

**响应**:
```json
{
  "skill_id": "web_search",
  "config": {
    "api_key": "***",
    "max_results": 10
  }
}
```

---

### POST /api/skills/config

更新技能配置。

**请求体**:
```json
{
  "skill_id": "web_search",
  "config": {
    "max_results": 20
  }
}
```

**响应**:
```json
{
  "success": true,
  "message": "配置已更新"
}
```

---

### POST /api/skills/install

安装新技能。

**请求体**:
```json
{
  "skill_url": "https://github.com/example/skill.git",
  "skill_name": "custom_skill"
}
```

**响应**:
```json
{
  "success": true,
  "message": "技能安装成功"
}
```

---

### POST /api/skills/reload

重新加载所有技能。

**响应**:
```json
{
  "success": true,
  "message": "技能已重新加载"
}
```

---

### GET /api/skills/marketplace

获取技能市场列表。

**响应**:
```json
{
  "marketplace": [
    {
      "name": "PDF Generator",
      "description": "生成PDF文档",
      "author": "SeeAgent",
      "downloads": 1000,
      "url": "https://github.com/seeagent/pdf-skill"
    }
  ]
}
```

---

## 文件接口

### GET /api/files

获取工作空间文件或目录内容。

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | 否 | 文件/目录路径，默认为根目录 |

**响应 (目录)**:
```json
{
  "type": "directory",
  "path": "/workspace",
  "items": [
    {
      "name": "documents",
      "type": "directory",
      "size": 0,
      "modified": "2024-01-01T00:00:00Z"
    },
    {
      "name": "readme.md",
      "type": "file",
      "size": 1024,
      "modified": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**响应 (文件)**: 返回文件内容（文本或二进制流）

---

## 上传接口

### POST /api/upload

上传文件到服务器。

**请求**: `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 要上传的文件 |

**响应**:
```json
{
  "success": true,
  "filename": "uploaded_file.pdf",
  "url": "/api/uploads/uploaded_file.pdf"
}
```

---

### GET /api/uploads/{filename}

获取已上传的文件。

**路径参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| filename | string | 文件名 |

**响应**: 返回文件内容（二进制流）

---

## 日志接口

### GET /api/logs/service

获取服务日志。

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| lines | int | 否 | 返回的日志行数，默认100 |
| level | string | 否 | 日志级别 (debug/info/warning/error) |

**响应**:
```json
{
  "logs": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "level": "info",
      "message": "Service started"
    }
  ]
}
```

---

## 系统接口

### GET /

根路径，返回服务状态页面。

**响应**: HTML 页面

---

### POST /api/shutdown

关闭服务。

**响应**:
```json
{
  "success": true,
  "message": "服务正在关闭"
}
```

---

## 附录

### 前端 API 客户端使用示例

```typescript
import { apiPostStream } from '@/api/client'

// 发送聊天消息（流式）
await apiPostStream(
  '/chat',
  { message: '你好' },
  (event) => {
    console.log('SSE Event:', event)
  },
  (error) => {
    console.error('Error:', error)
  },
  () => {
    console.log('Stream completed')
  }
)
```

### 错误码说明

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
