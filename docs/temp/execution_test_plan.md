# 多任务编排功能测试执行计划

> 版本: v1.0
> 日期: 2026-03-04
> 基于文档: docs/orchestration260303/

---

## 1. 项目背景

### 1.1 需求概述

基于 `docs/orchestration260303/` 下的三个文档，建立一套多任务编排机制的测试计划：

- **multitask_requirement_structured.md**: 需求整理，定义 MainAgent、SubAgent、TaskSession 三大核心角色
- **multitask_techdesign.md**: 技术设计，详细描述架构与实现方案
- **多任务简洁设计描述.md**: 简洁对齐版，便于快速理解

### 1.2 核心测试目标

验证多任务编排机制的正确性：
1. **MainAgent 消息路由**: 场景匹配 → 任务创建 → 步骤分发
2. **SubAgent 步骤执行**: 独立进程、独立对话历史、工具可见集合裁剪
3. **TaskSession 生命周期**: 步骤调度、上下文传递、用户确认
4. **前端可视化**: 三栏布局、任务卡片、步骤进度展示

### 1.3 Demo Skills 测试工具

| Skill | 功能 | 验证场景 |
|-------|------|---------|
| `demo-echo-json` | JSON 回显 + trace 信息 | 验证 `run_skill_script` 调用链路与参数传递 |
| `demo-context-hash` | 文本摘要生成 (sha256) | 验证步骤上下文注入与用户编辑生效 |
| `demo-json-diff` | JSON 对比 (before/after) | 验证 Edit/Confirm 后的数据流 |
| `demo-schema-check` | Schema 校验 (required/type) | 验证步骤输出稳定性与多轮交互修复 |

---

## 2. 测试环境准备

### 2.1 环境要求

```
- Python 3.12+
- Node.js 18+
- Chrome 浏览器 (最新版)
- Chrome DevTools / Chrome 扩展调试环境
```

### 2.2 依赖安装

```bash
# 后端依赖
cd /Users/zd/agents/openakita-main
source venv/bin/activate
pip install -r requirements.txt

# 前端依赖
cd webapps/seeagent-webui
npm install
```

### 2.3 服务启动

```bash
# 终端 1: 启动后端 API 服务
cd /Users/zd/agents/openakita-main
python -m openakita.api.server

# 终端 2: 启动前端开发服务
cd webapps/seeagent-webui
npm run dev

# 终端 3: 启动 WebSocket 服务 (如有独立服务)
python -m openakita.api.websocket
```

---

## 3. 单元测试计划

### 3.1 Demo Skills 脚本验证

**目的**: 确保 4 个 demo skill 脚本独立运行正常

#### 3.1.1 demo-echo-json 测试

```bash
# 测试用例 1: 基本 JSON 回显
python skills/demo-echo-json/scripts/echo.py --json '{"test":"value","trace_id":"t-001"}'
# 预期输出: {"ok":true,"received_at":"...","payload":{"test":"value","trace_id":"t-001"},"trace_id":"t-001"}

# 测试用例 2: 大输出测试 (--repeat)
python skills/demo-echo-json/scripts/echo.py --json '{"data":"x"}' --repeat 10
# 预期: payload 包含 __repeat__: 10

# 测试用例 3: 错误 JSON
python skills/demo-echo-json/scripts/echo.py --json 'invalid'
# 预期: stderr 输出错误信息，返回码 2
```

#### 3.1.2 demo-context-hash 测试

```bash
# 测试用例 1: SHA256 默认算法
python skills/demo-context-hash/scripts/hash.py --json '{"text":"hello"}'
# 预期输出: {"ok":true,"algorithm":"sha256","digest":"2cf24dba...","length":5}

# 测试用例 2: MD5 算法
python skills/demo-context-hash/scripts/hash.py --json '{"text":"hello","algorithm":"md5"}'
# 预期输出: {"ok":true,"algorithm":"md5","digest":"5d41402abc4b2a76b9719d911017c592","length":5}

# 测试用例 3: 空文本
python skills/demo-context-hash/scripts/hash.py --json '{"text":""}'
# 预期: digest 为空字符串的哈希值
```

#### 3.1.3 demo-json-diff 测试

```bash
# 测试用例 1: 字段修改
python skills/demo-json-diff/scripts/diff.py --json '{"before":{"a":1},"after":{"a":2}}'
# 预期输出: {"ok":true,"changed_paths":["a"],"counts":{"added":0,"removed":0,"modified":1},...}

# 测试用例 2: 字段新增
python skills/demo-json-diff/scripts/diff.py --json '{"before":{"a":1},"after":{"a":1,"b":2}}'
# 预期: changed_paths 包含 "b", counts.added = 1

# 测试用例 3: 字段删除
python skills/demo-json-diff/scripts/diff.py --json '{"before":{"a":1,"b":2},"after":{"a":1}}'
# 预期: changed_paths 包含 "b", counts.removed = 1

# 测试用例 4: 数组变化
python skills/demo-json-diff/scripts/diff.py --json '{"before":{"arr":[1,2]},"after":{"arr":[1,3]}}'
# 预期: changed_paths 包含 "arr.[1]"
```

#### 3.1.4 demo-schema-check 测试

```bash
# 测试用例 1: demo_draft_v1 合法数据
python skills/demo-schema-check/scripts/check.py --json '{"schema_id":"demo_draft_v1","data":{"title":"标题","bullets":["a","b"]}}'
# 预期输出: {"ok":true,"errors":[]}

# 测试用例 2: demo_draft_v1 缺少必填字段
python skills/demo-schema-check/scripts/check.py --json '{"schema_id":"demo_draft_v1","data":{"title":"标题"}}'
# 预期输出: {"ok":false,"errors":["missing: bullets"]}

# 测试用例 3: demo_final_v1 合法数据
python skills/demo-schema-check/scripts/check.py --json '{"schema_id":"demo_final_v1","data":{"title":"标题","bullets":["a"],"approved":true}}'
# 预期输出: {"ok":true,"errors":[]}

# 测试用例 4: demo_final_v1 缺少 approved
python skills/demo-schema-check/scripts/check.py --json '{"schema_id":"demo_final_v1","data":{"title":"标题","bullets":["a"]}}'
# 预期输出: {"ok":false,"errors":["missing: approved"]}
```

### 3.2 Skill 调用集成测试

**目的**: 通过 `run_skill_script` 工具调用 demo skills

```python
# 测试代码示例 (需在实际测试中实现)
async def test_skill_integration():
    # 通过 Agent 的 skill 工具调用
    result = await run_skill_script(
        skill_name="demo-echo-json",
        script_name="echo.py",
        args=["--json", json.dumps({"test": "integration"})]
    )
    assert result["ok"] == True
```

---

## 4. 多任务编排流程测试

### 4.1 测试场景设计

基于技术设计文档的 "最佳实践场景" 概念，设计以下测试场景：

#### 场景 A: 三步文档处理流程

```
Step 1 (analyze): 分析输入文本，输出 {analysis: "..."}
    ↓ 使用 demo-context-hash 生成分析摘要
Step 2 (review): 基于分析结果，输出 {review: {...}}
    ↓ 使用 demo-schema-check 校验输出格式
Step 3 (finalize): 生成最终文档，输出 {document: "..."}
    ↓ 使用 demo-json-diff 对比用户编辑前后变化
```

**测试数据流**:

```
用户输入: "请帮我分析并整理这份技术文档..."
    ↓
MainAgent 识别场景 → 创建 TaskSession
    ↓
Step 1 SubAgent 执行:
  - 调用 demo-context-hash(text="技术文档内容...")
  - 输出: {"analysis": "...", "hash": "abc123..."}
  - 用户确认
    ↓
Step 2 SubAgent 执行:
  - 接收 Step 1 输出作为上下文
  - 调用 demo-schema-check 验证输出格式
  - 输出: {"review": {...}}
  - 用户确认
    ↓
Step 3 SubAgent 执行:
  - 接收 Step 2 输出
  - 用户可编辑输出
  - 调用 demo-json-diff(before=原始, after=编辑后)
  - 输出最终文档
    ↓
任务完成，销毁所有 SubAgent
```

### 4.2 MainAgent 消息路由测试

#### 4.2.1 场景匹配测试

```python
async def test_scene_matching():
    """测试 MainAgent 场景匹配逻辑"""
    # 测试 1: 无任务时匹配最佳实践
    response = await main_agent.chat("帮我处理文档")
    assert "任务卡片" in response or "确认" in response

    # 测试 2: 有活跃任务时路由到 SubAgent
    # (需先创建任务)
    response = await main_agent.chat("继续下一步")
    # 预期路由到当前步骤的 SubAgent
```

#### 4.2.2 任务状态流转测试

```python
async def test_task_state_flow():
    """测试任务状态机"""
    # PENDING → RUNNING → WAITING_USER → RUNNING → ... → COMPLETED
    task = await create_task("test-task-001")
    assert task.status == "PENDING"

    await start_task(task)
    assert task.status == "RUNNING"

    await sub_agent.complete_step()
    assert task.status == "WAITING_USER"

    await user_confirm()
    assert task.status == "RUNNING"

    # ... 最终
    assert task.status == "COMPLETED"
```

### 4.3 SubAgent 步骤执行测试

#### 4.3.1 独立对话历史测试

```python
async def test_subagent_isolation():
    """测试 SubAgent 对话历史隔离"""
    # 创建多个 SubAgent
    sub1 = await create_sub_agent("step-1")
    sub2 = await create_sub_agent("step-2")

    # sub1 发送消息
    await sub1.chat("这是步骤1的消息")

    # sub2 不应该看到 sub1 的消息
    messages2 = sub2.get_messages()
    assert len(messages2) == 0  # 或仅包含系统消息
```

#### 4.3.2 工具可见集合测试

```python
async def test_tool_visibility():
    """测试工具可见集合裁剪"""
    # 配置 SubAgent 只能使用 demo skills
    sub_agent = await create_sub_agent(
        "step-1",
        tools=["run_skill_script"],
        skills=["demo-echo-json", "demo-context-hash"]
    )

    # 尝试调用不在可见集合的工具
    result = await sub_agent.execute("请使用 shell 工具执行命令")
    # 预期: SubAgent 拒绝或报告能力边界
    assert "超出能力范围" in result or "不可用" in result
```

### 4.4 上下文传递测试

```python
async def test_context_propagation():
    """测试步骤间上下文传递"""
    # Step 1 输出
    step1_output = {
        "analysis": "这是分析结果",
        "hash": "abc123..."
    }

    # 用户确认
    await task_session.complete_step("step-1", step1_output)

    # Step 2 应该收到上下文
    sub_agent_2 = await get_sub_agent("step-2")
    system_prompt = sub_agent_2.get_system_prompt()

    # 预期系统提示词包含 Step 1 输出
    assert "analysis" in system_prompt
    assert "这是分析结果" in system_prompt
```

---

## 5. 前端可视化测试 (Chrome)

### 5.1 测试工具

- **Chrome DevTools**: 元素检查、网络请求监控
- **Chrome Extension**: 自定义扩展或 Playwright
- **Playwright**: 自动化 E2E 测试

### 5.2 三栏布局测试

#### 5.2.1 左侧面板测试

**测试点**:
1. 最佳实践任务列表显示 (最多 5 行)
2. "更多" 入口跳转功能
3. 会话列表正常显示

**Chrome 测试步骤**:

```
1. 打开 Chrome DevTools (F12)
2. 导航到 Elements 面板
3. 检查左侧面板 DOM 结构:
   - 确认 .task-list 或 .best-practice-list 元素存在
   - 确认最多显示 5 个任务项
   - 确认 "更多" 按钮可点击
4. 点击 "更多"，验证右侧区域展示全部卡片
```

#### 5.2.2 中间对话区测试

**测试点**:
1. 主对话区保持现有功能
2. 任务卡片正确显示
3. SubAgent 对话状态显示

**Chrome 测试步骤**:

```
1. 在主对话框输入触发最佳实践的请求
2. 检查任务卡片 DOM:
   - 简短描述
   - SubAgent 名称
   - 确认按钮
3. 点击确认，检查右侧任务区出现
4. 检查 "正在与 [步骤名称] SubAgent 对话" 提示
```

#### 5.2.3 右侧任务区测试

**测试点**:
1. 步骤卡片显示
2. 任务卡片上下部分结构
3. 最后一步输出编辑功能

**Chrome 测试步骤**:

```
1. 检查右侧面板结构:
   - 上部: SubAgent 名字/说明/状态列表
   - 下部: 最后一步输出 + 编辑区
2. 测试编辑功能:
   - 修改输出内容
   - 点击保存
   - 验证内容已更新
3. 验证步骤总结在主对话框显示
```

### 5.3 任务状态可视化测试

#### 5.3.1 进度显示测试

```javascript
// Playwright 测试代码
test('任务进度显示', async ({ page }) => {
  // 创建任务
  await page.click('[data-testid="create-task"]');

  // 检查进度指示器
  const progress = await page.textContent('[data-testid="step-progress"]');
  expect(progress).toContain('1/3'); // 第一步

  // 完成第一步
  await page.click('[data-testid="confirm-step-1"]');

  // 检查进度更新
  const progress2 = await page.textContent('[data-testid="step-progress"]');
  expect(progress2).toContain('2/3'); // 第二步
});
```

#### 5.3.2 状态颜色测试

```
状态颜色预期:
- PENDING: 灰色
- RUNNING: 蓝色 (动态)
- WAITING_USER: 橙色
- COMPLETED: 绿色
- CANCELLED: 红色
```

### 5.4 WebSocket 实时更新测试

```javascript
// 测试 WebSocket 连接与状态同步
test('WebSocket 状态同步', async ({ page }) => {
  // 监听 WebSocket 消息
  await page.evaluate(() => {
    window.wsMessages = [];
    const ws = new WebSocket('ws://localhost:8765');
    ws.onmessage = (e) => window.wsMessages.push(JSON.parse(e.data));
  });

  // 触发状态变更
  await page.click('[data-testid="start-task"]');

  // 等待 WebSocket 消息
  await page.waitForFunction(() =>
    window.wsMessages.some(m => m.type === 'task_status_update')
  );

  // 验证 UI 更新
  const status = await page.textContent('[data-testid="task-status"]');
  expect(status).toBe('RUNNING');
});
```

### 5.5 Chrome 扩展辅助测试

#### 5.5.1 推荐扩展

1. **React DevTools**: 检查 React 组件状态
2. **Redux DevTools**: 检查状态管理
3. **WebSocket King Client**: 测试 WebSocket 消息

#### 5.5.2 自定义测试扩展

创建简单的 Chrome 扩展用于测试：

```javascript
// manifest.json
{
  "manifest_version": 3,
  "name": "OpenAkita Test Helper",
  "version": "1.0",
  "permissions": ["activeTab", "scripting"],
  "action": {
    "default_popup": "popup.html"
  }
}

// popup.js
document.getElementById('checkTask').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    function: checkTaskElements
  });
});

function checkTaskElements() {
  const results = {
    taskList: !!document.querySelector('.task-list'),
    taskCard: !!document.querySelector('.task-card'),
    stepProgress: !!document.querySelector('.step-progress'),
    editArea: !!document.querySelector('.edit-area')
  };
  console.log('Task Elements Check:', results);
  alert(JSON.stringify(results, null, 2));
}
```

---

## 6. E2E 测试用例

### 6.1 完整流程测试

```typescript
// e2e/multitask.spec.ts
import { test, expect } from '@playwright/test';

test.describe('多任务编排 E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
  });

  test('完整三步文档处理流程', async ({ page }) => {
    // 1. 创建任务
    await page.fill('[data-testid="chat-input"]', '请帮我分析并整理这份技术文档');
    await page.press('[data-testid="chat-input"]', 'Enter');

    // 2. 等待任务卡片出现
    await page.waitForSelector('[data-testid="task-card"]');

    // 3. 确认开始任务
    await page.click('[data-testid="confirm-task"]');

    // 4. 等待 Step 1 完成
    await page.waitForSelector('[data-testid="step-status"][data-status="WAITING_USER"]');

    // 5. 用户确认 Step 1
    const step1Output = await page.textContent('[data-testid="step-output"]');
    expect(step1Output).toContain('analysis');

    await page.click('[data-testid="confirm-step"]');

    // 6. 等待 Step 2
    await page.waitForSelector('[data-testid="step-status"][data-step="2"]');

    // 7. 用户编辑 Step 2 输出
    await page.fill('[data-testid="edit-output"]', '用户编辑的内容');
    await page.click('[data-testid="save-edit"]');

    // 8. 继续 Step 3
    await page.click('[data-testid="confirm-step"]');

    // 9. 验证任务完成
    await page.waitForSelector('[data-testid="task-status"][data-status="COMPLETED"]');

    // 10. 检查最终输出
    const finalOutput = await page.textContent('[data-testid="final-output"]');
    expect(finalOutput).toContain('document');
  });

  test('任务取消流程', async ({ page }) => {
    // 创建并启动任务
    await page.fill('[data-testid="chat-input"]', '处理文档');
    await page.press('[data-testid="chat-input"]', 'Enter');
    await page.waitForSelector('[data-testid="task-card"]');
    await page.click('[data-testid="confirm-task"]');

    // 取消任务
    await page.click('[data-testid="cancel-task"]');

    // 验证状态
    const status = await page.getAttribute('[data-testid="task-status"]', 'data-status');
    expect(status).toBe('CANCELLED');
  });

  test('步骤切换功能', async ({ page }) => {
    // 创建多步任务
    // ...

    // 点击切换到 Step 1
    await page.click('[data-testid="step-tab"][data-step="1"]');

    // 验证切换成功
    const activeStep = await page.getAttribute('[data-testid="active-step"]', 'data-step');
    expect(activeStep).toBe('1');
  });
});
```

### 6.2 Demo Skills 集成测试

```typescript
test('Demo Skills 在多任务中调用', async ({ page }) => {
  // 创建任务，使用 demo skills
  await page.fill('[data-testid="chat-input"]',
    '使用 demo-context-hash 分析这段文本: Hello World');
  await page.press('[data-testid="chat-input"]', 'Enter');

  // 等待 SubAgent 执行
  await page.waitForSelector('[data-testid="skill-output"]');

  // 验证输出包含 hash
  const output = await page.textContent('[data-testid="skill-output"]');
  expect(output).toMatch(/[a-f0-9]{64}/); // SHA256 格式
});
```

---

## 7. 性能与压力测试

### 7.1 并发 SubAgent 测试

```python
async def test_concurrent_subagents():
    """测试多个 SubAgent 并发执行"""
    tasks = []
    for i in range(5):
        task = create_and_run_sub_agent(f"step-{i}")
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    # 验证所有任务完成
    assert all(r.status == "completed" for r in results)
```

### 7.2 大输出处理测试

```python
async def test_large_output():
    """测试大输出处理"""
    # 使用 --repeat 生成大输出
    result = await run_skill_script(
        skill_name="demo-echo-json",
        script_name="echo.py",
        args=["--json", '{"data":"x"}', "--repeat", "1000"]
    )

    # 验证输出被正确截断或处理
    assert result["ok"] == True
```

---

## 8. 测试执行清单

### 8.1 执行顺序

```
Phase 1: 单元测试 (Day 1)
├── [ ] 3.1 Demo Skills 脚本验证
│   ├── [ ] demo-echo-json (4 个测试用例)
│   ├── [ ] demo-context-hash (3 个测试用例)
│   ├── [ ] demo-json-diff (4 个测试用例)
│   └── [ ] demo-schema-check (4 个测试用例)
└── [ ] 3.2 Skill 调用集成测试

Phase 2: 编排流程测试 (Day 2-3)
├── [ ] 4.1 测试场景设计
├── [ ] 4.2 MainAgent 消息路由测试
├── [ ] 4.3 SubAgent 步骤执行测试
└── [ ] 4.4 上下文传递测试

Phase 3: 前端可视化测试 (Day 4-5)
├── [ ] 5.2 三栏布局测试
│   ├── [ ] 左侧面板测试
│   ├── [ ] 中间对话区测试
│   └── [ ] 右侧任务区测试
├── [ ] 5.3 任务状态可视化测试
├── [ ] 5.4 WebSocket 实时更新测试
└── [ ] 5.5 Chrome 扩展辅助测试

Phase 4: E2E 测试 (Day 6)
├── [ ] 6.1 完整流程测试
└── [ ] 6.2 Demo Skills 集成测试

Phase 5: 性能测试 (Day 7)
├── [ ] 7.1 并发 SubAgent 测试
└── [ ] 7.2 大输出处理测试
```

### 8.2 测试报告模板

```
## 测试执行报告

**日期**: YYYY-MM-DD
**测试人员**:
**环境**:

### 测试结果摘要

| 模块 | 用例数 | 通过 | 失败 | 跳过 |
|------|--------|------|------|------|
| Demo Skills | 15 | - | - | - |
| 编排流程 | 10 | - | - | - |
| 前端可视化 | 12 | - | - | - |
| E2E | 5 | - | - | - |
| 性能 | 2 | - | - | - |

### 缺陷列表

| ID | 描述 | 严重程度 | 状态 |
|----|------|----------|------|
| - | - | - | - |

### 建议

-
```

---

## 9. 附录

### 9.1 测试数据

```json
{
  "sample_analysis": {
    "title": "测试文档标题",
    "content": "这是一段测试内容...",
    "metadata": {
      "author": "test",
      "date": "2026-03-04"
    }
  },
  "sample_review": {
    "title": "审查报告",
    "bullets": ["问题1", "问题2", "问题3"],
    "approved": false
  },
  "sample_final": {
    "title": "最终文档",
    "bullets": ["要点1", "要点2"],
    "approved": true,
    "document": "最终内容..."
  }
}
```

### 9.2 参考链接

- 需求文档: `docs/orchestration260303/multitask_requirement_structured.md`
- 技术设计: `docs/orchestration260303/multitask_techdesign.md`
- 简洁描述: `docs/orchestration260303/多任务简洁设计描述.md`
- Demo Skills: `skills/demo-*`
- 前端代码: `webapps/seeagent-webui/`
- 测试代码: `tests/`