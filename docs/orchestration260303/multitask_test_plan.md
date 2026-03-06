# 多任务编排系统测试计划

> 版本: v1.0
> 日期: 2026-03-05
> 项目: test_multi
> 状态: 规划完成

---

## 1. 测试目标

验证多任务编排系统的核心功能：
- 任务创建与管理
- SubAgent 步骤执行
- 上下文传递机制
- 用户确认与编辑功能
- 前端可视化交互

---

## 2. 测试环境

### 2.1 后端服务

```bash
# 启动 OpenAkita 服务
export PYTHONPATH=./src
openakita serve

# 验证服务状态
curl http://127.0.0.1:18900/
```

### 2.2 前端测试环境

- **URL**: http://127.0.0.1:18900
- **Chrome 插件**: OpenAkita Chrome Extension
- **测试框架**: Playwright

### 2.3 Demo Skills 验证

```bash
# 验证 demo skills 可用
PYTHONPATH=./src python -c "
from openakita.tools.definitions.skills import list_skills
skills = list_skills()
demo_skills = [s for s in skills if 'demo' in s.lower()]
print('Demo Skills:', demo_skills)
"
```

---

## 3. 测试场景配置

### 3.1 已创建的测试场景

| 场景文件 | 场景 ID | 步骤数 | 测试重点 |
|---------|---------|--------|---------|
| `test-demo-flow.yaml` | test-demo-flow | 4 | Demo skills 调用、上下文传递 |
| `test-edit-flow.yaml` | test-edit-flow | 3 | 编辑功能、diff 对比 |
| `test-context-pass.yaml` | test-context-pass | 2 | 上下文传递 |
| `test-user-confirm.yaml` | test-user-confirm | 3 | 用户确认 |
| `code-review.yaml` | code-review | 3 | 实际场景 |
| `pdf-form-processing.yaml` | pdf-form-processing | 3 | PDF 处理 |

### 3.2 触发关键词

| 场景 | 触发关键词 |
|------|-----------|
| test-demo-flow | "测试demo流程", "demo flow test" |
| test-edit-flow | "测试编辑流程", "edit flow test" |
| code-review | "代码审查", "审查代码", "code review" |
| pdf-form-processing | "PDF表单", "填写PDF" |

---

## 4. 后端测试用例

### 4.1 Phase 1: 后端单元测试

#### TEST-001: ScenarioRegistry 单元测试

**文件**: `tests/orchestration/test_scenario_registry.py`

```python
import pytest
from openakita.orchestration import ScenarioRegistry
from openakita.orchestration.models import ScenarioDefinition, TriggerPattern, TriggerType

class TestScenarioRegistry:
    """场景注册表测试"""

    def test_register_scenario(self):
        """测试场景注册"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="测试场景",
            steps=[],
        )
        assert registry.register(scenario) == True
        assert registry.count() == 1

    def test_unregister_scenario(self):
        """测试场景注销"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="测试场景",
            steps=[],
        )
        registry.register(scenario)
        assert registry.unregister("test-scenario") == True
        assert registry.count() == 0

    def test_match_regex_pattern(self):
        """测试正则匹配"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="code-review",
            name="代码审查",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.REGEX,
                    pattern=r"(审查|review).*(代码|code)",
                    priority=1,
                )
            ],
            steps=[],
        )
        registry.register(scenario)

        result = registry.match_from_dialog("帮我审查一下代码")
        assert result is not None
        assert result.scenario.scenario_id == "code-review"
        assert result.confidence >= 0.9

    def test_match_keyword_pattern(self):
        """测试关键词匹配"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="pdf-form",
            name="PDF表单处理",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["PDF表单", "填写PDF"],
                    priority=2,
                )
            ],
            steps=[],
        )
        registry.register(scenario)

        result = registry.match_from_dialog("帮我处理这个PDF表单")
        assert result is not None
        assert result.scenario.scenario_id == "pdf-form"
```

#### TEST-002: TaskSession 单元测试

**文件**: `tests/orchestration/test_task_session.py`

```python
import pytest
from openakita.orchestration import TaskSession
from openakita.orchestration.models import TaskStatus

class TestTaskSession:
    """任务会话测试"""

    @pytest.fixture
    def task_session(self):
        """创建测试任务会话"""
        # ... fixture setup
        pass

    async def test_task_lifecycle(self, task_session):
        """测试任务生命周期"""
        assert task_session.state.status == TaskStatus.PENDING

        await task_session.start()
        assert task_session.state.status == TaskStatus.RUNNING

        await task_session.complete()
        assert task_session.state.status == TaskStatus.COMPLETED

    async def test_step_execution(self, task_session):
        """测试步骤执行"""
        await task_session.start()

        # 验证步骤按顺序执行
        assert task_session.state.current_step_index == 0

        # 等待第一步完成
        # ...

    async def test_context_storage(self, task_session):
        """测试上下文存储"""
        task_session.context["test_key"] = {"data": "test_value"}

        assert "test_key" in task_session.context
        assert task_session.context["test_key"]["data"] == "test_value"
```

#### TEST-003: 上下文传递机制测试

**文件**: `tests/orchestration/test_context_passing.py`

```python
import pytest

class TestContextPassing:
    """上下文传递机制测试"""

    async def test_single_step_no_context(self):
        """测试单步骤无上下文"""
        pass

    async def test_two_step_context_pass(self):
        """测试两步骤上下文传递"""
        # Step 1: echo -> 生成 JSON
        # Step 2: hash -> 使用 Step 1 的输出
        pass

    async def test_multi_step_chain(self):
        """测试多步骤链式传递"""
        # Step 1 -> Step 2 -> Step 3
        # 验证每一步都能访问前序输出
        pass

    async def test_template_variable_replacement(self):
        """测试模板变量替换"""
        # 验证 {{context.xxx}} 被正确替换
        pass
```

#### TEST-004: 用户确认机制测试

**文件**: `tests/orchestration/test_user_confirmation.py`

```python
import pytest

class TestUserConfirmation:
    """用户确认机制测试"""

    async def test_step_wait_for_confirmation(self):
        """测试步骤等待确认"""
        pass

    async def test_confirm_and_continue(self):
        """测试确认后继续执行"""
        pass

    async def test_edit_and_confirm(self):
        """测试编辑后确认"""
        pass

    async def test_cancel_confirmation(self):
        """测试取消确认"""
        pass
```

---

### 4.2 Phase 2: Demo Skills 集成测试

#### TEST-005~008: Demo Skills 测试

**文件**: `tests/orchestration/test_demo_skills.py`

```python
import pytest
import json

class TestDemoSkills:
    """Demo Skills 测试"""

    async def test_demo_echo_json(self):
        """测试 demo-echo-json 技能"""
        # 调用技能
        result = await run_skill_script(
            skill_name="demo-echo-json",
            script_name="echo.py",
            args=["--json", '{"trace_id":"test-001"}']
        )

        # 验证输出
        data = json.loads(result)
        assert data["ok"] == True
        assert data["trace_id"] == "test-001"

    async def test_demo_context_hash(self):
        """测试 demo-context-hash 技能"""
        result = await run_skill_script(
            skill_name="demo-context-hash",
            script_name="hash.py",
            args=["--json", '{"text":"hello","algorithm":"sha256"}']
        )

        data = json.loads(result)
        assert data["ok"] == True
        assert len(data["digest"]) == 64  # SHA256 hex length

    async def test_demo_json_diff(self):
        """测试 demo-json-diff 技能"""
        result = await run_skill_script(
            skill_name="demo-json-diff",
            script_name="diff.py",
            args=["--json", '{"before":{"a":1},"after":{"a":2}}']
        )

        data = json.loads(result)
        assert data["ok"] == True
        assert "a" in data["changed_paths"]

    async def test_demo_schema_check(self):
        """测试 demo-schema-check 技能"""
        # 测试校验通过
        result = await run_skill_script(
            skill_name="demo-schema-check",
            script_name="check.py",
            args=["--json", '{"schema_id":"demo_draft_v1","data":{"title":"t","bullets":["a"]}}']
        )
        data = json.loads(result)
        assert data["ok"] == True

        # 测试校验失败
        result = await run_skill_script(
            skill_name="demo-schema-check",
            script_name="check.py",
            args=["--json", '{"schema_id":"demo_draft_v1","data":{"title":"t"}}']
        )
        data = json.loads(result)
        assert data["ok"] == False
```

---

### 4.3 Phase 3: API 端点测试

#### TEST-009~011: API 测试

**文件**: `tests/orchestration/test_api.py`

```python
import pytest
from httpx import AsyncClient

class TestTasksAPI:
    """任务 API 测试"""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(base_url="http://127.0.0.1:18900") as client:
            yield client

    async def test_create_task(self, client):
        """测试创建任务"""
        response = await client.post("/api/tasks", json={
            "message": "测试demo流程",
            "session_id": "test-session-001"
        })
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    async def test_list_tasks(self, client):
        """测试列出任务"""
        response = await client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data

    async def test_start_task(self, client):
        """测试启动任务"""
        # 先创建任务
        create_resp = await client.post("/api/tasks", json={
            "scenario_id": "test-demo-flow",
            "session_id": "test-session-002"
        })
        task_id = create_resp.json()["task_id"]

        # 启动任务
        response = await client.post(f"/api/tasks/{task_id}/start")
        assert response.status_code == 200

    async def test_cancel_task(self, client):
        """测试取消任务"""
        # 创建并启动任务
        # ...

        # 取消任务
        response = await client.post(f"/api/tasks/{task_id}/cancel")
        assert response.status_code == 200
        assert response.json()["success"] == True

    async def test_confirm_step(self, client):
        """测试确认步骤"""
        response = await client.post(f"/api/tasks/{task_id}/confirm", json={
            "step_id": "validate"
        })
        assert response.status_code == 200


class TestScenariosAPI:
    """场景 API 测试"""

    async def test_list_scenarios(self, client):
        """测试列出场景"""
        response = await client.get("/api/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_get_scenario(self, client):
        """测试获取场景详情"""
        response = await client.get("/api/scenarios/test-demo-flow")
        assert response.status_code == 200
        data = response.json()
        assert data["scenario_id"] == "test-demo-flow"

    async def test_start_scenario(self, client):
        """测试启动场景"""
        response = await client.post("/api/scenarios/test-demo-flow/start", json={
            "session_id": "test-session-003"
        })
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
```

---

### 4.4 Phase 4: 端到端测试

**文件**: `tests/orchestration/test_e2e.py`

```python
import pytest

class TestEndToEnd:
    """端到端测试"""

    async def test_demo_flow_scenario(self):
        """测试 test-demo-flow 场景"""
        # 1. 创建任务
        task = await orchestrator.create_task_manual(
            scenario_id="test-demo-flow",
            session_id="e2e-test-001"
        )

        # 2. 启动任务
        await orchestrator.start_task(task.state.task_id)

        # 3. 等待完成
        await asyncio.sleep(30)

        # 4. 验证结果
        assert task.state.status == TaskStatus.COMPLETED
        assert "echo_result" in task.context
        assert "hash_result" in task.context
        assert "validation_result" in task.context
        assert "final_report" in task.context

    async def test_edit_flow_scenario(self):
        """测试 test-edit-flow 场景"""
        # 1. 创建并启动任务
        # 2. 等待第一步完成
        # 3. 编辑输出
        # 4. 确认进入下一步
        # 5. 验证 diff 结果
        pass

    async def test_code_review_scenario(self):
        """测试 code-review 场景"""
        pass
```

---

## 5. 前端可视化测试

### 5.1 Phase 5: 前端组件测试

#### FE-TEST-001: 任务卡片组件测试

**文件**: `tests/e2e/task_card.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('任务卡片组件', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://127.0.0.1:18900');
  });

  test('任务卡片渲染', async ({ page }) => {
    // 创建任务
    await page.click('[data-testid="new-task-btn"]');
    await page.fill('[data-testid="message-input"]', '测试demo流程');
    await page.click('[data-testid="send-btn"]');

    // 等待任务卡片
    await page.waitForSelector('[data-testid="task-card"]', { timeout: 5000 });

    // 验证任务卡片显示
    const card = await page.locator('[data-testid="task-card"]');
    await expect(card).toBeVisible();
  });

  test('进度显示', async ({ page }) => {
    // 创建多步骤任务
    // ...

    // 验证进度更新
    const progress = await page.locator('[data-testid="step-progress"]');
    await expect(progress).toHaveText(/1\/4/);
  });

  test('状态变化', async ({ page }) => {
    // 观察状态变化
    // ...
  });

  test('取消功能', async ({ page }) => {
    // 点击取消按钮
    await page.click('[data-testid="cancel-task-btn"]');

    // 确认取消
    await page.click('[data-testid="confirm-cancel-btn"]');

    // 验证状态
    const status = await page.locator('[data-testid="task-status"]');
    await expect(status).toHaveText('已取消');
  });
});
```

#### FE-TEST-002: 步骤输出编辑器测试

**文件**: `tests/e2e/step_editor.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('步骤输出编辑器', () => {
  test('输出显示', async ({ page }) => {
    // 等待步骤完成
    await page.waitForSelector('[data-testid="step-output"]');

    // 验证 JSON 格式化
    const output = await page.locator('[data-testid="step-output"]');
    await expect(output).toBeVisible();
  });

  test('编辑模式', async ({ page }) => {
    // 点击编辑按钮
    await page.click('[data-testid="edit-output-btn"]');

    // 验证编辑器激活
    const editor = await page.locator('[data-testid="output-editor"]');
    await expect(editor).toBeEditable();
  });

  test('保存编辑', async ({ page }) => {
    // 编辑内容
    await page.fill('[data-testid="output-editor"]', '{"modified": true}');

    // 保存
    await page.click('[data-testid="save-edit-btn"]');

    // 验证保存成功
    await page.waitForSelector('[data-testid="save-success"]');
  });
});
```

#### FE-TEST-003: 对话触发场景测试

**文件**: `tests/e2e/dialog_trigger.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('对话触发场景', () => {
  test('触发词匹配', async ({ page }) => {
    await page.goto('http://127.0.0.1:18900');

    // 输入触发词
    await page.fill('[data-testid="message-input"]', '测试demo流程');
    await page.click('[data-testid="send-btn"]');

    // 验证场景匹配
    await page.waitForSelector('[data-testid="scenario-match"]', { timeout: 5000 });
    const match = await page.locator('[data-testid="scenario-match"]');
    await expect(match).toContainText('Demo 技能流程测试');
  });

  test('任务创建', async ({ page }) => {
    // 触发并确认创建
    // ...

    // 验证任务卡片出现
    await page.waitForSelector('[data-testid="task-card"]');
  });

  test('SubAgent 状态显示', async ({ page }) => {
    // 验证 SubAgent 状态
    const status = await page.locator('[data-testid="subagent-status"]');
    await expect(status).toContainText('正在与');
  });
});
```

---

### 5.2 Phase 6: Chrome 插件专用测试

#### CHROME-TEST-001~003: Chrome 插件测试

**文件**: `tests/e2e/chrome_extension.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('Chrome 插件', () => {
  test('插件安装和连接', async ({ page, context }) => {
    // 安装插件
    // 注意：需要配置 Playwright 加载 Chrome 插件

    // 验证连接成功
    await page.waitForSelector('[data-testid="connection-status"]');
    const status = await page.locator('[data-testid="connection-status"]');
    await expect(status).toHaveText('已连接');
  });

  test('SSE 流式响应', async ({ page }) => {
    // 发送消息
    await page.fill('[data-testid="message-input"]', '测试demo流程');
    await page.click('[data-testid="send-btn"]');

    // 验证流式消息
    const messages = await page.locator('[data-testid="stream-message"]');
    await expect(messages.first()).toBeVisible({ timeout: 5000 });
  });

  test('多任务并发', async ({ page }) => {
    // 创建多个任务
    // ...

    // 验证并行执行
    // ...
  });
});
```

---

### 5.3 Phase 7: 测试基础设施

#### INFRA-001: Playwright 配置

**文件**: `tests/e2e/playwright.config.ts`

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'http://127.0.0.1:18900',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    command: 'openakita serve',
    url: 'http://127.0.0.1:18900',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
```

#### INFRA-002: 测试辅助函数

**文件**: `tests/conftest.py`

```python
import pytest
import asyncio
from openakita.orchestration import TaskOrchestrator, ScenarioRegistry, SubAgentManager

@pytest.fixture
async def orchestrator():
    """创建测试用编排器"""
    registry = ScenarioRegistry()
    manager = SubAgentManager()
    orchestrator = TaskOrchestrator(
        scenario_registry=registry,
        sub_agent_manager=manager,
    )
    await orchestrator.initialize()
    yield orchestrator
    await orchestrator.shutdown()


@pytest.fixture
def test_scenario():
    """返回测试场景定义"""
    return {
        "scenario_id": "test-demo-flow",
        "name": "Demo 技能流程测试",
        "steps": [
            {"step_id": "echo", "name": "生成测试数据"},
            {"step_id": "hash", "name": "计算数据指纹"},
            {"step_id": "validate", "name": "校验数据结构"},
            {"step_id": "summary", "name": "生成测试报告"},
        ]
    }
```

---

## 6. 测试执行命令

### 6.1 后端测试

```bash
# 运行所有后端测试
PYTHONPATH=./src pytest tests/orchestration/ -v

# 运行特定测试
PYTHONPATH=./src pytest tests/orchestration/test_scenario_registry.py -v

# 运行带覆盖率
PYTHONPATH=./src pytest tests/orchestration/ --cov=src/openakita/orchestration --cov-report=html
```

### 6.2 前端测试

```bash
# 安装依赖
cd tests/e2e
npm install

# 运行测试
npx playwright test

# 运行特定测试
npx playwright test task_card.spec.ts

# 打开测试报告
npx playwright show-report
```

### 6.3 完整测试流程

```bash
# 1. 启动后端服务
openakita serve &

# 2. 等待服务就绪
sleep 5

# 3. 运行后端测试
PYTHONPATH=./src pytest tests/orchestration/ -v

# 4. 运行前端测试
cd tests/e2e && npx playwright test

# 5. 生成覆盖率报告
PYTHONPATH=./src pytest tests/orchestration/ --cov=src/openakita/orchestration --cov-report=html
```

---

## 7. 测试报告模板

| 测试套件 | 通过 | 失败 | 跳过 | 通过率 |
|---------|-----|------|-----|--------|
| Phase 1: 后端单元测试 | - | - | - | -% |
| Phase 2: Demo Skills | - | - | - | -% |
| Phase 3: API 端点 | - | - | - | -% |
| Phase 4: 端到端 | - | - | - | -% |
| Phase 5: 前端组件 | - | - | - | -% |
| Phase 6: Chrome 插件 | - | - | - | -% |
| **总计** | **-** | **-** | **-** | **-%** |

---

## 8. 附录

### A. 测试数据准备

```bash
# 确保测试场景已加载
curl http://127.0.0.1:18900/api/scenarios

# 预期的场景列表
# - test-demo-flow
# - test-edit-flow
# - test-context-pass
# - test-user-confirm
# - code-review
# - pdf-form-processing
```

### B. 环境变量

```bash
export OPENAKITA_TEST_MODE=true
export OPENAKITA_LOG_LEVEL=DEBUG
export OPENAKITA_SCENARIO_PATH=scenarios
```

### C. 常用调试命令

```bash
# 查看所有场景
curl http://127.0.0.1:18900/api/scenarios

# 查看所有任务
curl http://127.0.0.1:18900/api/tasks

# 查看特定任务
curl http://127.0.0.1:18900/api/tasks/{task_id}

# 查看任务上下文
curl http://127.0.0.1:18900/api/tasks/{task_id}/context
```