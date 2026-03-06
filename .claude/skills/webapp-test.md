name: webapp-test
description: Test OpenAkita webapp with Playwright browser automation. Use when testing API endpoints, multi-Agent mode, or plan mode functionality. Supports simple chat, multi-skill calls, and plan triggering test cases.
---

# OpenAkita Webapp Testing Guide

This skill guides you through testing the OpenAkita webapp using Playwright browser automation.

## Prerequisites

Before running tests, ensure:
1. Backend service is running (`openakita serve` on port 18900)
2. Frontend dev server is running (`pnpm dev` on port 5175)
3. Environment is configured (`.env` file)

## Test Categories

### 1. Simple Chat Test

Tests basic chat functionality:
- Send a simple message
- Verify streaming response
- Check session management

### 2. Multi-Skill Call Test

Tests tool/skill invocation:
- Send a task requiring tool use
- Verify tool_call_start/tool_call_end events
- Check result handling

### 3. Plan Mode Test

Tests plan creation and execution:
- Send a multi-step task
- Verify plan_created event
- Check step execution and progress

## Test Execution

### Step 1: Start Backend Service

```bash
cd /Users/zd/agents/openakita-main
source venv/bin/activate
openakita serve
```

Verify service is running:
```bash
curl http://localhost:18900/api/health
```

### Step 2: Start Frontend Dev Server

```bash
cd /Users/zd/agents/openakita-main/webapps/seeagent-webui
pnpm dev
```

Verify frontend is running:
```bash
curl http://localhost:5175
```

### Step 3: Run Playwright Tests

```bash
cd /Users/zd/agents/openakita-main/webapps/seeagent-webui

# Run all tests
pnpm test:e2e

# Run with UI for debugging
pnpm test:e2e:ui

# Run specific test file
npx playwright test e2e/plan-mode.spec.ts
```

## Using Playwright MCP Tools

When the frontend is running, you can use Playwright MCP tools directly:

### Navigate to Webapp

```
Use mcp__playwright__browser_navigate to http://localhost:5175
```

### Test Simple Chat

1. Take a snapshot to understand page structure:
   ```
   mcp__playwright__browser_snapshot
   ```

2. Click "New Chat" button:
   ```
   mcp__playwright__browser_click on "New Chat" button
   ```

3. Type a simple message:
   ```
   mcp__playwright__browser_type into textarea: "你好，请介绍一下你自己"
   ```

4. Click send button:
   ```
   mcp__playwright__browser_click on "send" button
   ```

5. Wait for and verify response:
   ```
   mcp__playwright__browser_wait_for text containing response
   ```

### Test Multi-Agent Mode

1. Verify orchestration is enabled:
   ```bash
   grep ORCHESTRATION_ENABLED /Users/zd/agents/openakita-main/.env
   ```

2. Send a task that might trigger worker distribution:
   ```
   Type: "帮我分析这个项目的代码结构，并生成一份文档"
   ```

3. Check backend logs for:
   ```
   "MasterAgent 模式: 分发任务到 Worker"
   "Distributing task xxx to worker xxx"
   ```

### Test Plan Mode

1. Send a multi-step task:
   ```
   Type: "请打开百度网站，搜索北京今天天气，然后截图保存"
   ```

2. Verify plan creation:
   ```
   Wait for "任务计划" heading to appear
   Check for step status icons (⏳, ▶️, ✅)
   ```

3. Monitor execution:
   ```
   Check progress indicator: "进度: X/Y 完成"
   Wait for completion: "100%" or "🎉"
   ```

## Test Assertions

### API Health Check

```bash
# Health endpoint
curl http://localhost:18900/api/health

# Expected: {"status": "ok", ...}
```

### Chat API Test

```bash
# Send chat request
curl -X POST http://localhost:18900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'

# Expected: SSE stream with text_delta events
```

### Multi-Agent Status

```bash
# Check if MasterAgent is running
curl http://localhost:18900/api/health

# Look for orchestration info in response
```

## Troubleshooting

### Backend Not Starting

1. Check if port 18900 is in use:
   ```bash
   lsof -i :18900
   ```

2. Check Python dependencies:
   ```bash
   pip install -e .
   ```

### Frontend Not Starting

1. Check if port 5175 is in use:
   ```bash
   lsof -i :5175
   ```

2. Reinstall dependencies:
   ```bash
   cd webapps/seeagent-webui
   pnpm install
   ```

### Tests Timing Out

1. Increase timeout in `playwright.config.ts`
2. Check backend logs for errors
3. Verify LLM API credentials are set

## Checklist

- [ ] Backend service running on port 18900
- [ ] Frontend dev server running on port 5175
- [ ] Health check returns OK
- [ ] Simple chat test passes
- [ ] Multi-skill call test passes
- [ ] Plan mode test passes
- [ ] Multi-Agent mode logs show worker distribution (if enabled)