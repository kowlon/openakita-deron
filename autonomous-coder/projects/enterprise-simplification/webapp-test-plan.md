# SeeAgent Web UI 详细测试计划

> 创建日期: 2026-02-24
> 更新日期: 2026-02-24
> 基于需求: `docs/webapp-requirement/front_web_requirement.md`
> 项目路径: `webapps/seeagent-webui/`

---

## 一、测试概述

### 1.1 测试目标

确保 SeeAgent Web UI 在企业级场景下功能完整、交互正确：
1. 会话可视化正确
2. 步骤可控机制正常
3. 计时器准确
4. 文件卡片功能完整
5. Edit 模式交互正确

### 1.2 测试策略

```
┌─────────────────────────────────────────────────────────────┐
│                      测试金字塔                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌─────────┐                              │
│                    │ E2E 测试 │  ← Chrome DevTools / 手动    │
│                    └─────────┘                              │
│               ┌───────────────────┐                         │
│               │ 前端集成测试       │  ← React Testing Lib    │
│               └───────────────────┘                         │
│          ┌─────────────────────────────┐                    │
│          │ 后端 API 测试                │  ← pytest          │
│          └─────────────────────────────┘                    │
│     ┌───────────────────────────────────────┐               │
│     │ 单元测试 (前端组件 + 后端模块)          │  ← vitest    │
│     └───────────────────────────────────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 测试环境

| 环境 | 说明 | 启动命令 |
|------|------|----------|
| 后端服务 | OpenAkita API | `python -m openakita --config config/enterprise.yaml` |
| 前端服务 | React Dev Server | `cd webapps/seeagent-webui && pnpm dev` |
| Chrome 插件 | React DevTools | Chrome 扩展商店安装 |
| 网络代理 | Charles/Fiddler | 可选，用于抓包分析 |

---

## 二、后端 API 测试

### 2.1 测试环境准备

```bash
# 1. 启动后端服务
cd /Users/zd/agents/openakita-deron
python -m openakita --config config/enterprise.yaml

# 2. 验证服务运行
curl http://localhost:8000/health

# 3. 验证 API 端点
curl http://localhost:8000/api/chat -X POST -H "Content-Type: application/json" -d '{"message": "test"}'
```

### 2.2 SSE 事件流测试

**测试目标**: 验证后端正确发送所有 SSE 事件

**测试脚本** (`tests/api/test_sse_events.py`):
```python
import pytest
import httpx
import asyncio

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_sse_event_sequence():
    """测试 SSE 事件顺序"""
    events_received = []

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat",
            json={"message": "帮我查查今天天气"},
            timeout=60.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event = line[6:]
                    events_received.append(event)

    # 验证事件顺序
    assert any("thinking_start" in e for e in events_received), "缺少 thinking_start"
    assert any("text_delta" in e for e in events_received), "缺少 text_delta"
    assert any("done" in e for e in events_received), "缺少 done"

@pytest.mark.asyncio
async def test_ttft_timing():
    """测试 TTFT 时间记录"""
    import time

    start_time = time.time()
    first_token_time = None

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat",
            json={"message": "你好"},
            timeout=60.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and "text_delta" in line:
                    first_token_time = time.time()
                    break

    assert first_token_time is not None, "未收到首 token"
    ttft = first_token_time - start_time
    print(f"TTFT: {ttft:.2f}s")
    assert ttft < 5.0, f"TTFT 过长: {ttft:.2f}s"

@pytest.mark.asyncio
async def test_tool_call_events():
    """测试工具调用事件"""
    events = []

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat",
            json={"message": "帮我搜索曾德龙"},
            timeout=120.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(line[6:])

    # 验证工具调用事件
    tool_starts = [e for e in events if "tool_call_start" in e]
    tool_ends = [e for e in events if "tool_call_end" in e]

    assert len(tool_starts) > 0, "缺少 tool_call_start 事件"
    assert len(tool_ends) > 0, "缺少 tool_call_end 事件"
    assert len(tool_starts) == len(tool_ends), "工具调用开始/结束事件数量不匹配"

@pytest.mark.asyncio
async def test_artifact_event():
    """测试文件生成事件"""
    events = []

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat",
            json={"message": "帮我生成一个测试PDF文件"},
            timeout=120.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(line[6:])

    # 验证 artifact 事件
    artifact_events = [e for e in events if "artifact" in e.lower()]
    assert len(artifact_events) > 0, "缺少 artifact 相关事件"
```

**运行后端测试**:
```bash
cd /Users/zd/agents/openakita-deron
pytest tests/api/test_sse_events.py -v
```

### 2.3 后端验收标准

| 测试项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| SSE 连接 | 连接建立成功，事件流持续输出 | `curl -N http://localhost:8000/api/chat` |
| 事件顺序 | thinking_start → tool_call_start → tool_call_end → text_delta → done | pytest 测试 |
| TTFT 时间 | < 3s（简单查询） | pytest 测试 |
| 工具调用事件 | 成对出现，数量匹配 | pytest 测试 |
| Artifact 事件 | 文件生成后正确发送 | pytest 测试 |

---

## 三、前端 Chrome DevTools 测试

### 3.1 测试环境准备

```bash
# 1. 启动前端服务
cd /Users/zd/agents/openakita-deron/webapps/seeagent-webui
pnpm install
pnpm dev

# 2. 打开 Chrome 浏览器
# 访问 http://localhost:5174

# 3. 打开 Chrome DevTools
# 快捷键: Cmd+Option+I (Mac) / Ctrl+Shift+I (Windows)

# 4. 安装 React Developer Tools 扩展
# Chrome 商店搜索 "React Developer Tools"
```

### 3.2 TEST-WEB-001: TTFT 计时器锁定测试

**测试目标**: 验证 TTFT 在首 token 后锁定，不随后续步骤变化

**前置条件**:
- 后端服务运行中
- 前端服务运行中
- Chrome DevTools 打开

**测试步骤**:

| 步骤 | 操作 | 预期结果 | 验证方法 |
|------|------|----------|----------|
| 1 | 打开 Chrome DevTools → Network 标签 | 显示网络请求面板 | 目视确认 |
| 2 | 在输入框输入 "帮我查查今天天气" | 输入框显示文字 | 目视确认 |
| 3 | 点击发送按钮 | 消息发送，计时器开始 | 目视确认 |
| 4 | 等待首 token 输出 | TTFT 显示具体值（如 0.85s） | 记录此值 |
| 5 | 等待后续步骤执行 | 步骤卡片逐个出现 | 目视确认 |
| 6 | 再次查看 TTFT 值 | 仍为 0.85s（不变） | 与步骤4对比 |

**Chrome DevTools 辅助验证**:
```
1. Network 标签 → 筛选 "EventStream" 类型
2. 点击 SSE 连接 → EventStream 标签
3. 记录首个 text_delta 事件的时间戳
4. 计算 TTFT = text_delta时间 - 请求发起时间
5. 与界面显示的 TTFT 对比，应一致
```

**验收标准**:
- [ ] TTFT 在首 token 后显示具体值
- [ ] 后续步骤执行期间 TTFT 值不变
- [ ] Network 标签显示 SSE 事件流
- [ ] 界面 TTFT 与 Network 计算值一致（误差 < 0.1s）

---

### 3.3 TEST-WEB-002: 中间步骤显示测试

**测试目标**: 验证复杂任务的步骤正确显示和过滤

**测试用例**: 发送 "帮我查查曾德龙是谁，并帮我写入到pdf文件里"

**预期显示的步骤**:
```
步骤1: 🧠 意图分析
       识别到需要搜索"曾德龙"相关信息并输出为PDF

步骤2: 🔍 网络搜索
       正在搜索"曾德龙"相关信息...

步骤3: 📄 PDF输出
       正在生成PDF文件...

步骤4: ✅ 总结
       已完成搜索并输出PDF文件
```

**不应显示的内部步骤**:
- Plan 管理 (create_plan, update_plan)
- 文件读取 (read_file)
- 命令执行 (run_shell, bash)
- 技能信息获取 (get_skill_info)
- 结果交付 (deliver_artifacts)

**测试步骤**:

| 步骤 | 操作 | 预期结果 | 验证方法 |
|------|------|----------|----------|
| 1 | 发送测试消息 | 消息显示在对话区 | 目视确认 |
| 2 | 观察步骤卡片 | 逐个显示核心步骤 | 目视确认 |
| 3 | 检查步骤内容 | 每个步骤有标题、摘要、计时 | 目视确认 |
| 4 | 验证步骤类型图标 | 意图分析=🧠, 搜索=🔍, PDF=📄 | 目视确认 |
| 5 | 统计步骤数量 | 3-5 个核心步骤 | 计数确认 |

**Chrome DevTools 辅助验证**:
```
1. React Developer Tools → Components 标签
2. 找到 StepTimeline 组件
3. 查看 steps 属性，确认 category 字段
4. 核心步骤 category = "core"
5. 内部步骤 category = "internal"（已被过滤）
```

**验收标准**:
- [ ] 核心步骤正确显示
- [ ] 内部步骤被过滤隐藏
- [ ] 步骤状态图标正确（等待中/执行中/已完成/失败）
- [ ] 步骤类型图标正确
- [ ] 每个步骤有独立的计时显示

---

### 3.4 TEST-WEB-003: SSE 事件处理测试

**测试目标**: 验证所有 SSE 事件类型正确处理

**Chrome DevTools 验证步骤**:

| 步骤 | 操作 | 验证内容 |
|------|------|----------|
| 1 | Network → 筛选 EventStream | 看到 SSE 连接 |
| 2 | 点击连接 → EventStream 标签 | 实时显示事件流 |
| 3 | 发送消息，观察事件 | 记录事件顺序 |
| 4 | 对照事件与 UI 响应 | 确认事件触发正确 UI 更新 |

**事件类型与 UI 响应对照表**:

| 事件类型 | 预期 UI 响应 | 验证方法 |
|---------|--------------|----------|
| `thinking_start` | 无步骤卡片显示 | DevTools 看事件，界面无变化 |
| `tool_call_start` | 创建步骤卡片，状态=执行中 | 界面显示新步骤，计时开始 |
| `tool_call_end` | 更新步骤状态=已完成，停止计时 | 步骤显示 ✓，计时锁定 |
| `text_delta` | AI 回复文字追加 | 文字逐步显示 |
| `done` | 总计时停止，任务完成 | 计时器显示最终值 |
| `artifact_created` | 创建文件卡片 | 文件卡片出现 |

**Console 辅助验证**:
```javascript
// 在 Console 中运行，监控事件
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  if (args[0].includes('/api/chat')) {
    console.log('[SSE] Request:', args);
  }
  return originalFetch(...args);
};
```

**验收标准**:
- [ ] thinking_start 事件不显示步骤卡片
- [ ] tool_call_start 创建步骤卡片
- [ ] tool_call_end 更新步骤状态
- [ ] text_delta 触发文字流式输出
- [ ] done 事件停止总计时
- [ ] artifact_created 创建文件卡片

---

### 3.5 TEST-WEB-004: 文件卡片组件测试

**测试目标**: 验证 Artifact 组件正确显示和功能

**测试用例**: 发送 "帮我生成一个PDF文件，内容是测试文档"

**测试步骤**:

| 步骤 | 操作 | 预期结果 | 验证方法 |
|------|------|----------|----------|
| 1 | 发送消息，等待完成 | 任务完成 | 目视确认 |
| 2 | 检查文件卡片 | 显示 PDF 卡片 | 目视确认 |
| 3 | 验证文件图标 | 📄 红色图标 | 目视确认 |
| 4 | 验证文件名 | 显示完整文件名 | 目视确认 |
| 5 | 验证文件大小 | 显示 KB/MB | 目视确认 |
| 6 | 点击下载按钮 | 文件下载成功 | 检查下载目录 |
| 7 | 点击预览按钮 | 预览窗口打开 | 目视确认 |

**不同文件类型验证**:

| 文件类型 | 测试消息 | 预期图标 | 预览支持 |
|---------|---------|---------|---------|
| PDF | "生成PDF" | 📄 红色 | ✅ |
| Word | "生成Word文档" | 📝 蓝色 | ❌ |
| Excel | "生成Excel表格" | 📊 绿色 | ❌ |
| 图片 | "生成图片" | 🖼️ 紫色 | ✅ |

**Chrome DevTools 辅助验证**:
```
1. React Developer Tools → Components
2. 找到 ArtifactCard 组件
3. 查看 props:
   - type: "pdf"
   - filename: "xxx.pdf"
   - size: 字节数
   - downloadUrl: 下载链接
```

**验收标准**:
- [ ] 文件卡片正确显示
- [ ] 图标根据类型正确显示
- [ ] 文件名和大小正确
- [ ] 下载功能正常
- [ ] PDF/图片预览正常

---

### 3.6 TEST-WEB-005: 步骤计时器测试

**测试目标**: 验证三种计时器（TTFT、总计时、步骤计时）正确工作

**测试用例**: 发送多步骤任务 "帮我搜索马斯克最新新闻，然后整理成PDF"

**三种计时器验证**:

| 计时器 | 开始时机 | 停止时机 | 验证方法 |
|--------|---------|---------|----------|
| TTFT | 消息发送 | 首 token 到达 | 与 Network 对比 |
| 总计时 | 消息发送 | done 事件 | 最终值显示 |
| 步骤计时 | 步骤开始 | 步骤完成 | 每步独立值 |

**测试步骤**:

| 步骤 | 操作 | 验证内容 |
|------|------|----------|
| 1 | 发送消息 | 计时器从 0 开始 |
| 2 | 等待首 token | TTFT 锁定，记录值 |
| 3 | 观察步骤1计时 | 步骤完成后锁定 |
| 4 | 观察步骤2计时 | 步骤完成后锁定 |
| 5 | 任务完成 | 总计时锁定 |
| 6 | 验证关系 | 总计时 ≈ TTFT + Σ(步骤增量) |

**Console 辅助验证**:
```javascript
// 监控计时器状态
setInterval(() => {
  const timers = document.querySelectorAll('[data-testid*="timer"]');
  timers.forEach(t => console.log(t.dataset.testid, t.textContent));
}, 500);
```

**验收标准**:
- [ ] TTFT 在首 token 后锁定
- [ ] 步骤计时独立且准确
- [ ] 总计时在 done 后锁定
- [ ] 计时值与 Network 时间戳一致（误差 < 0.5s）

---

### 3.7 TEST-WEB-006: Edit 模式交互测试

**测试目标**: 验证 Edit 模式完整交互流程

**前置条件**: 切换到 Edit 模式（顶部工具栏）

**测试用例**: "查一下曾德龙是谁，然后写成pdf文件"

**测试步骤**:

| 步骤 | 操作 | 预期结果 | 验证方法 |
|------|------|----------|----------|
| 1 | 切换到 Edit 模式 | 模式按钮高亮 | 目视确认 |
| 2 | 发送测试消息 | 消息显示 | 目视确认 |
| 3 | 等待步骤1完成 | 进入编辑状态（暂停） | 显示"等待用户确认" |
| 4 | 点击步骤卡片 | 右侧面板打开 | 显示编辑界面 |
| 5 | 取消勾选一个结果 | 结果取消选中 | 勾选框变化 |
| 6 | 点击删除按钮 | 结果被删除 | 结果消失 |
| 7 | 点击"添加自定义内容" | 输入框出现 | 可输入内容 |
| 8 | 输入自定义内容 | 内容添加到列表 | 显示新内容 |
| 9 | 点击"确认，继续下一步" | 步骤2开始执行 | 新步骤出现 |
| 10 | 验证步骤2使用编辑后数据 | 结果符合预期 | 检查输出内容 |

**右侧面板验证要点**:
```
┌─────────────────────────────────────────┐
│  Step Details                    [×]    │
├─────────────────────────────────────────┤
│  [Completed] [Tool] ID: abc123          │
│  Step 1: 新闻搜索                        │
│  Duration: 3.25s                        │
├─────────────────────────────────────────┤
│  📝 Edit 模式 - 等待用户确认              │  ← 状态提示
│                                         │
│  Selected 3 of 4 results    [Select All]│  ← 选择统计
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ ☑️ 结果1...              [🗑️]    │  │  ← 可勾选/删除
│  └───────────────────────────────────┘  │
│                                         │
│  [+ 添加自定义内容]                      │  ← 添加功能
│                                         │
│  [确认，继续下一步 →]                    │  ← 确认按钮
└─────────────────────────────────────────┘
```

**验收标准**:
- [ ] Edit 模式切换正常
- [ ] 步骤完成后暂停
- [ ] 右侧面板显示编辑界面
- [ ] 勾选/取消勾选正常
- [ ] 删除结果正常
- [ ] 添加自定义内容正常
- [ ] 确认后继续执行
- [ ] 编辑结果传递给下一步

---

### 3.8 TEST-WEB-007: 会话管理测试

**测试目标**: 验证多轮对话和会话管理功能

**测试步骤**:

| 步骤 | 操作 | 预期结果 | 验证方法 |
|------|------|----------|----------|
| 1 | 点击"+"创建新会话 | 新会话创建，左侧显示 | 目视确认 |
| 2 | 发送消息 "你好" | 消息显示，AI 回复 | 目视确认 |
| 3 | 等待会话摘要生成 | 左侧显示摘要标题 | 目视确认 |
| 4 | 发送第二条消息 | 消息追加到对话末尾 | 目视确认 |
| 5 | 点击"+"创建第二个会话 | 第二个会话显示 | 目视确认 |
| 6 | 切换到第一个会话 | 历史对话加载 | 目视确认 |
| 7 | 删除第一个会话 | 会话从列表移除 | 目视确认 |

**会话摘要验证**:
```
发送: "帮我查查曾德龙是谁，并帮我写入到pdf文件里"
预期摘要: "查询曾德龙信息并输出PDF" (10-20字)
```

**验收标准**:
- [ ] 新会话创建正常
- [ ] 会话摘要自动生成
- [ ] 消息追加不替换
- [ ] 会话切换正常
- [ ] 历史对话正确加载
- [ ] 会话删除正常

---

## 四、自动化测试用例

### 4.1 后端单元测试

**文件**: `tests/unit/test_context.py`

```python
import pytest
from openakita.context.enterprise import EnterpriseContextManager
from openakita.context.enterprise.config import ContextConfig

class TestEnterpriseContextManager:
    def test_initialize_system_context(self):
        """测试系统上下文初始化"""
        config = ContextConfig()
        manager = EnterpriseContextManager(config)
        manager.initialize(
            identity="我是企业助手",
            rules=["规则1", "规则2"],
            tools_manifest="工具列表"
        )

        assert manager.system_ctx is not None
        assert "企业助手" in manager.system_ctx.to_prompt()

    def test_task_lifecycle(self):
        """测试任务生命周期"""
        config = ContextConfig()
        manager = EnterpriseContextManager(config)
        manager.initialize(identity="test", rules=[], tools_manifest="")

        # 开始任务
        manager.start_task("task-001", "tenant-001", "search", "搜索任务")
        assert "task-001" in manager.task_contexts

        # 结束任务
        manager.end_task("task-001")
        assert "task-001" not in manager.task_contexts

    def test_conversation_sliding_window(self):
        """测试对话滑动窗口"""
        config = ContextConfig(max_conversation_rounds=5)
        manager = EnterpriseContextManager(config)
        manager.initialize(identity="test", rules=[], tools_manifest="")

        session_id = "session-001"

        # 添加 10 轮对话
        for i in range(10):
            manager.add_message(session_id, "user", f"消息{i}")
            manager.add_message(session_id, "assistant", f"回复{i}")

        conv_ctx = manager.conversation_contexts.get(session_id)
        assert conv_ctx is not None
        # 验证滑动窗口生效
        assert conv_ctx._count_rounds() <= 5
```

### 4.2 前端单元测试

**文件**: `webapps/seeagent-webui/tests/unit/stepFilter.test.ts`

```typescript
import { describe, it, expect } from 'vitest'
import { shouldShowStep } from '../../src/utils/stepFilter'

describe('Step Filter', () => {
  it('should hide internal steps', () => {
    const step = {
      id: '1',
      title: 'read_file',
      category: 'internal',
      status: 'completed',
      type: 'tool'
    }
    expect(shouldShowStep(step)).toBe(false)
  })

  it('should show core steps', () => {
    const step = {
      id: '2',
      title: 'web_search',
      category: 'core',
      status: 'completed',
      type: 'tool'
    }
    expect(shouldShowStep(step)).toBe(true)
  })

  it('should hide plan management steps', () => {
    const step = {
      id: '3',
      title: 'create_plan',
      category: 'internal',
      status: 'completed',
      type: 'tool'
    }
    expect(shouldShowStep(step)).toBe(false)
  })
})
```

**文件**: `webapps/seeagent-webui/tests/unit/timer.test.ts`

```typescript
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTimer } from '../../src/hooks/useTimer'

describe('Timer', () => {
  it('should lock TTFT after first token', () => {
    const { result } = renderHook(() => useTimer())

    act(() => {
      result.current.start()
    })

    // 模拟首 token
    act(() => {
      result.current.lockTTFT()
    })

    const ttftValue = result.current.ttft

    // 等待一段时间
    act(() => {
      vi.advanceTimersByTime(2000)
    })

    // TTFT 应该不变
    expect(result.current.ttft).toBe(ttftValue)
  })

  it('should calculate total time correctly', () => {
    const { result } = renderHook(() => useTimer())

    act(() => {
      result.current.start()
    })

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    act(() => {
      result.current.stop()
    })

    expect(result.current.total).toBeCloseTo(3, 1)
  })
})
```

### 4.3 E2E 测试 (Playwright)

**文件**: `webapps/seeagent-webui/tests/e2e/chat.spec.ts`

```typescript
import { test, expect } from '@playwright/test'

test.describe('Chat Flow E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5174')
  })

  test('should display steps for complex task', async ({ page }) => {
    // 发送消息
    await page.fill('[data-testid="chat-input"]', '帮我查查曾德龙是谁')
    await page.click('[data-testid="send-button"]')

    // 等待步骤显示
    await page.waitForSelector('[data-testid="step-card"]', { timeout: 30000 })

    // 验证步骤数量 > 0
    const steps = await page.$$('[data-testid="step-card"]')
    expect(steps.length).toBeGreaterThan(0)

    // 验证步骤状态图标
    const statusIcon = await page.$('[data-testid="step-status-icon"]')
    expect(statusIcon).toBeTruthy()
  })

  test('should lock TTFT after first token', async ({ page }) => {
    await page.fill('[data-testid="chat-input"]', '你好')
    await page.click('[data-testid="send-button"]')

    // 等待 TTFT 显示
    await page.waitForSelector('[data-testid="ttft-value"]', { timeout: 30000 })

    // 获取 TTFT 值
    const ttft = await page.textContent('[data-testid="ttft-value"]')

    // 等待更多输出
    await page.waitForTimeout(2000)

    // 验证 TTFT 不变
    const ttftAfter = await page.textContent('[data-testid="ttft-value"]')
    expect(ttft).toBe(ttftAfter)
  })

  test('should create artifact card for PDF', async ({ page }) => {
    await page.fill('[data-testid="chat-input"]', '帮我生成一个测试PDF')
    await page.click('[data-testid="send-button"]')

    // 等待文件卡片
    await page.waitForSelector('[data-testid="artifact-card"]', { timeout: 120000 })

    // 验证文件类型图标
    const icon = await page.getAttribute('[data-testid="artifact-icon"]', 'data-type')
    expect(icon).toBe('pdf')

    // 测试下载
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="download-button"]')
    ])
    expect(download).toBeTruthy()
  })

  test('should work in Edit mode', async ({ page }) => {
    // 切换到 Edit 模式
    await page.click('[data-testid="mode-toggle"]')
    await page.click('text=Edit')

    // 发送消息
    await page.fill('[data-testid="chat-input"]', '帮我搜索马斯克')
    await page.click('[data-testid="send-button"]')

    // 等待编辑状态
    await page.waitForSelector('text=等待用户确认', { timeout: 60000 })

    // 点击步骤打开详情面板
    await page.click('[data-testid="step-card"]')

    // 验证编辑界面
    await page.waitForSelector('[data-testid="editable-result-list"]')

    // 取消勾选一个结果
    await page.click('[data-testid="result-checkbox"]:nth-child(2)')

    // 确认继续
    await page.click('text=确认，继续下一步')
  })
})
```

### 4.4 运行测试

```bash
# 后端测试
cd /Users/zd/agents/openakita-deron
pytest tests/unit/test_context.py -v
pytest tests/api/test_sse_events.py -v

# 前端单元测试
cd webapps/seeagent-webui
pnpm test

# 前端 E2E 测试
pnpm test:e2e

# 测试覆盖率
pnpm test:coverage
```

---

## 五、测试执行清单

### 5.1 后端测试清单

| ID | 测试项 | 方法 | 状态 |
|----|--------|------|------|
| API-001 | 健康检查接口 | curl | 待执行 |
| API-002 | SSE 连接建立 | curl -N | 待执行 |
| API-003 | 事件顺序验证 | pytest | 待执行 |
| API-004 | TTFT 时间记录 | pytest | 待执行 |
| API-005 | 工具调用事件 | pytest | 待执行 |
| API-006 | Artifact 事件 | pytest | 待执行 |
| API-007 | 上下文管理单元测试 | pytest | 待执行 |

### 5.2 前端 Chrome 测试清单

| ID | 测试项 | Chrome DevTools | 状态 |
|----|--------|-----------------|------|
| WEB-001 | TTFT 计时器锁定 | Network → EventStream | 待执行 |
| WEB-002 | 步骤显示和过滤 | React DevTools → Components | 待执行 |
| WEB-003 | SSE 事件处理 | Network → EventStream | 待执行 |
| WEB-004 | 文件卡片功能 | Components → ArtifactCard | 待执行 |
| WEB-005 | 步骤计时器 | Console 监控 | 待执行 |
| WEB-006 | Edit 模式交互 | 手动操作 | 待执行 |
| WEB-007 | 会话管理 | 手动操作 | 待执行 |

### 5.3 自动化测试清单

| ID | 测试项 | 框架 | 状态 |
|----|--------|------|------|
| AUTO-001 | 后端单元测试 | pytest | 待编写 |
| AUTO-002 | 前端单元测试 | vitest | 待编写 |
| AUTO-003 | E2E 测试 | Playwright | 待编写 |

---

## 六、验收标准总览

### 6.1 功能验收

| 功能 | 验收标准 | 测试方法 |
|------|----------|----------|
| TTFT 计时 | 首 token 后锁定，误差 < 0.1s | Chrome DevTools |
| 步骤显示 | 核心步骤显示，内部步骤隐藏 | 目视 + React DevTools |
| 文件卡片 | 正确显示，下载正常 | 目视 + 操作 |
| Edit 模式 | 完整交互流程正常 | 手动操作 |
| 会话管理 | 创建/切换/删除正常 | 手动操作 |

### 6.2 性能验收

| 指标 | 标准 | 测试方法 |
|------|------|----------|
| 首屏加载 | < 2s | Chrome DevTools → Performance |
| TTFT | < 3s | 界面计时器 |
| SSE 延迟 | < 100ms | Network → Timing |

### 6.3 兼容性验收

| 浏览器 | 版本 | 状态 |
|--------|------|------|
| Chrome | 最新版 | 待测试 |
| Firefox | 最新版 | 待测试 |
| Safari | 最新版 | 待测试 |
| Edge | 最新版 | 待测试 |

---

## 七、测试环境启动脚本

```bash
#!/bin/bash
# scripts/start-test-env.sh

echo "=== 启动测试环境 ==="

# 1. 启动后端
echo "启动后端服务..."
cd /Users/zd/agents/openakita-deron
python -m openakita --config config/enterprise.yaml &
BACKEND_PID=$!
sleep 3

# 2. 验证后端
echo "验证后端..."
curl -s http://localhost:8000/health || echo "后端启动失败"
sleep 2

# 3. 启动前端
echo "启动前端服务..."
cd webapps/seeagent-webui
pnpm dev &
FRONTEND_PID=$!
sleep 5

# 4. 输出信息
echo ""
echo "=== 测试环境已启动 ==="
echo "后端: http://localhost:8000 (PID: $BACKEND_PID)"
echo "前端: http://localhost:5174 (PID: $FRONTEND_PID)"
echo ""
echo "Chrome DevTools 测试步骤:"
echo "1. 打开 Chrome 浏览器"
echo "2. 访问 http://localhost:5174"
echo "3. 按 Cmd+Option+I 打开 DevTools"
echo "4. 切换到 Network 标签"
echo "5. 筛选 EventStream 类型"
echo ""

# 等待
wait
```

---

*文档版本: v2*
*更新时间: 2026-02-24*
