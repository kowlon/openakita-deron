# 企业级 Memory & Context 重构实施计划

> 创建日期: 2026-02-23
> 基于文档: `docs/memory-refactoring-enterprise.md` 和 `docs/context-refactoring-enterprise.md`

---

## 一、项目概述

### 1.1 目标

将 OpenAkita 的 Memory 和 Context 模块从 C 端用户场景重构为企业级应用场景：

| 维度 | C 端（现有） | 企业级（目标） |
|-----|------------|--------------|
| **Memory** | 全存储、AI 提取、向量搜索 | 任务导向、规则写入、轻量存储 |
| **Context** | LLM 压缩、被动触发、无限增长 | 滑动窗口、三层分离、可控生命周期 |

### 1.2 预期收益

- **延迟降低**：压缩从 2-5s 降到 <10ms
- **部署简化**：移除 ChromaDB 和 embedding 模型依赖
- **资源节省**：内存从 200-500MB 降到 10-50MB
- **多租户支持**：原生支持任务级隔离

### 1.3 重构范围

```
src/openakita/
├── memory/                  # 重构
│   ├── enterprise/          # 新增
│   └── legacy/              # 保留兼容
├── context/                 # 新增
│   ├── enterprise/          # 企业级实现
│   └── legacy/              # 兼容适配
└── config.py                # 更新配置
```

---

## 二、功能分解

### 2.1 Memory 重构任务

| ID | 任务 | 优先级 | 依赖 |
|----|------|--------|------|
| MEM-001 | 定义 MemoryBackend 协议 | P0 | - |
| MEM-002 | 实现 SystemRuleStore | P0 | MEM-001 |
| MEM-003 | 实现 TaskContextStore | P0 | MEM-001 |
| MEM-004 | 实现 SkillStore (可选) | P1 | MEM-001 |
| MEM-005 | 实现 EnterpriseMemoryRouter | P0 | MEM-002, MEM-003 |
| MEM-006 | 实现 LegacyMemoryBackend 适配器 | P0 | MEM-001 |
| MEM-007 | 更新配置系统 | P0 | MEM-005 |
| MEM-008 | 后端单元测试 | P0 | MEM-005 |
| MEM-009 | 集成测试 | P1 | MEM-008 |

### 2.2 Context 重构任务

| ID | 任务 | 优先级 | 依赖 |
|----|------|--------|------|
| CTX-001 | 定义 ContextBackend 协议 | P0 | - |
| CTX-002 | 实现 SystemContext | P0 | CTX-001 |
| CTX-003 | 实现 TaskContext | P0 | CTX-001 |
| CTX-004 | 实现 ConversationContext | P0 | CTX-001 |
| CTX-005 | 实现 EnterpriseContextManager | P0 | CTX-002, CTX-003, CTX-004 |
| CTX-006 | 实现 LegacyContextBackend 适配器 | P0 | CTX-001 |
| CTX-007 | 更新 Agent 集成 | P0 | CTX-005 |
| CTX-008 | 后端单元测试 | P0 | CTX-005 |
| CTX-009 | 集成测试 | P1 | CTX-008 |

### 2.3 端到端测试任务

| ID | 任务 | 优先级 | 依赖 |
|----|------|--------|------|
| E2E-001 | Memory 模块 Chrome 插件测试 | P0 | MEM-008 |
| E2E-002 | Context 模块 Chrome 插件测试 | P0 | CTX-008 |
| E2E-003 | 完整流程端到端测试 | P1 | E2E-001, E2E-002 |

---

## 三、详细实施步骤

### MEM-001: 定义 MemoryBackend 协议

**目标**: 创建抽象协议，支持多种后端实现

**文件**: `src/openakita/memory/protocol.py`

**代码规范**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MemoryBackend(Protocol):
    """Memory 后端协议"""

    async def get_injection_context(
        self, task_id: str, task_type: str, query: str
    ) -> str:
        """获取注入到系统提示的记忆上下文"""
        ...

    def record_step_completion(
        self, task_id: str, step_id: str, step_name: str, summary: str, variables: dict
    ) -> None:
        """记录步骤完成"""
        ...

    def record_error(
        self, task_id: str, step_id: str, error_type: str, error_message: str, resolution: str | None
    ) -> None:
        """记录错误"""
        ...

    def start_task(self, task_id: str, tenant_id: str, task_type: str, description: str) -> None:
        """开始任务"""
        ...

    def end_task(self, task_id: str) -> None:
        """结束任务"""
        ...

    def get_stats(self, task_id: str) -> dict:
        """获取统计信息"""
        ...
```

**验收步骤**:
1. 创建 `src/openakita/memory/protocol.py`
2. 定义 `MemoryBackend` 协议
3. 添加类型注解和文档字符串
4. 运行 `mypy src/openakita/memory/protocol.py` 确保类型正确

---

### MEM-002: 实现 SystemRuleStore

**目标**: 实现系统规则存储，管理业务规则

**文件**: `src/openakita/memory/enterprise/rules.py`

**数据结构**:
```python
@dataclass
class SystemRule:
    id: str
    category: RuleCategory
    content: str
    priority: int  # 1-10
    enabled: bool
    created_by: str
    created_at: datetime

class RuleCategory(Enum):
    COMPLIANCE = "compliance"
    SECURITY = "security"
    BUSINESS = "business"
    CUSTOM = "custom"
```

**验收步骤**:
1. 创建 `src/openakita/memory/enterprise/__init__.py`
2. 创建 `src/openakita/memory/enterprise/rules.py`
3. 实现 `SystemRule` 和 `RuleCategory`
4. 实现 `SystemRuleStore` 类
   - `load_from_yaml(path: str) -> None`
   - `load_from_json(path: str) -> None`
   - `get_enabled_rules() -> list[SystemRule]`
   - `get_rules_by_category(category: RuleCategory) -> list[SystemRule]`
5. 编写单元测试 `tests/memory/enterprise/test_rules.py`

**后端单元测试用例**:
```python
# tests/memory/enterprise/test_rules.py

import pytest
from openakita.memory.enterprise.rules import SystemRuleStore, RuleCategory, SystemRule

class TestSystemRuleStore:
    def test_load_from_yaml(self, tmp_path):
        """测试从 YAML 加载规则"""
        # 准备测试数据
        yaml_content = """
rules:
  - id: rule-001
    category: compliance
    content: "不允许存储敏感信息"
    priority: 10
    enabled: true
"""
        yaml_file = tmp_path / "rules.yaml"
        yaml_file.write_text(yaml_content)

        # 执行
        store = SystemRuleStore()
        store.load_from_yaml(str(yaml_file))

        # 验证
        rules = store.get_enabled_rules()
        assert len(rules) == 1
        assert rules[0].id == "rule-001"
        assert rules[0].category == RuleCategory.COMPLIANCE

    def test_get_rules_by_category(self):
        """测试按类别获取规则"""
        store = SystemRuleStore()
        store._rules = [
            SystemRule(id="1", category=RuleCategory.COMPLIANCE, content="c1", priority=10, enabled=True, created_by="admin", created_at=datetime.now()),
            SystemRule(id="2", category=RuleCategory.SECURITY, content="s1", priority=10, enabled=True, created_by="admin", created_at=datetime.now()),
        ]

        compliance_rules = store.get_rules_by_category(RuleCategory.COMPLIANCE)
        assert len(compliance_rules) == 1
        assert compliance_rules[0].id == "1"

    def test_disabled_rules_not_returned(self):
        """测试禁用的规则不返回"""
        store = SystemRuleStore()
        store._rules = [
            SystemRule(id="1", category=RuleCategory.COMPLIANCE, content="c1", priority=10, enabled=True, created_by="admin", created_at=datetime.now()),
            SystemRule(id="2", category=RuleCategory.COMPLIANCE, content="c2", priority=10, enabled=False, created_by="admin", created_at=datetime.now()),
        ]

        enabled_rules = store.get_enabled_rules()
        assert len(enabled_rules) == 1
        assert enabled_rules[0].id == "1"

    def test_rules_sorted_by_priority(self):
        """测试规则按优先级排序"""
        store = SystemRuleStore()
        store._rules = [
            SystemRule(id="1", category=RuleCategory.COMPLIANCE, content="low", priority=5, enabled=True, created_by="admin", created_at=datetime.now()),
            SystemRule(id="2", category=RuleCategory.COMPLIANCE, content="high", priority=10, enabled=True, created_by="admin", created_at=datetime.now()),
        ]

        rules = store.get_enabled_rules()
        assert rules[0].priority >= rules[1].priority
```

---

### MEM-003: 实现 TaskContextStore

**目标**: 实现任务上下文存储，管理任务级记忆

**文件**: `src/openakita/memory/enterprise/task_context.py`

**数据结构**:
```python
@dataclass
class TaskMemory:
    task_id: str
    tenant_id: str
    task_type: str
    task_description: str
    step_summaries: list[str]  # 最近 20 条
    key_variables: dict[str, str]  # 最多 50 个
    errors: list[ErrorEntry]
    created_at: datetime
    updated_at: datetime

@dataclass
class ErrorEntry:
    step_id: str
    error_type: str
    error_message: str
    retry_count: int
    resolution: str | None
```

**后端单元测试用例**:
```python
# tests/memory/enterprise/test_task_context.py

class TestTaskContextStore:
    def test_start_task(self):
        """测试开始任务"""
        store = TaskContextStore(backend="memory")
        store.start_task("task-001", "tenant-001", "search", "搜索曾德龙")

        ctx = store.get_context("task-001")
        assert ctx is not None
        assert ctx.task_id == "task-001"
        assert ctx.tenant_id == "tenant-001"
        assert ctx.task_type == "search"

    def test_end_task(self):
        """测试结束任务"""
        store = TaskContextStore(backend="memory")
        store.start_task("task-001", "tenant-001", "search", "搜索")

        store.end_task("task-001")

        ctx = store.get_context("task-001")
        assert ctx is None

    def test_record_step_completion(self):
        """测试记录步骤完成"""
        store = TaskContextStore(backend="memory")
        store.start_task("task-001", "tenant-001", "search", "搜索")

        store.record_step_completion(
            "task-001", "step-001", "网络搜索", "搜索完成，找到5条结果",
            {"query": "曾德龙"}
        )

        ctx = store.get_context("task-001")
        assert len(ctx.step_summaries) == 1
        assert "网络搜索" in ctx.step_summaries[0]
        assert ctx.key_variables["query"] == "曾德龙"

    def test_step_summaries_limit(self):
        """测试步骤摘要数量限制（最多20条）"""
        store = TaskContextStore(backend="memory")
        store.start_task("task-001", "tenant-001", "search", "搜索")

        # 添加 25 条
        for i in range(25):
            store.record_step_completion("task-001", f"step-{i}", f"步骤{i}", f"摘要{i}", {})

        ctx = store.get_context("task-001")
        assert len(ctx.step_summaries) == 20  # 保留最近 20 条
        assert "步骤24" in ctx.step_summaries[-1]  # 最后一条是最新的

    def test_record_error(self):
        """测试记录错误"""
        store = TaskContextStore(backend="memory")
        store.start_task("task-001", "tenant-001", "search", "搜索")

        store.record_error("task-001", "step-001", "NetworkError", "网络超时", None)
        store.record_error("task-001", "step-002", "TimeoutError", "请求超时", "重试成功")

        ctx = store.get_context("task-001")
        assert len(ctx.errors) == 2
        assert ctx.errors[0].error_type == "NetworkError"
        assert ctx.errors[1].resolution == "重试成功"

    def test_tenant_isolation(self):
        """测试租户隔离"""
        store = TaskContextStore(backend="memory")

        # 创建两个租户的任务
        store.start_task("task-001", "tenant-A", "search", "租户A的任务")
        store.start_task("task-002", "tenant-B", "search", "租户B的任务")

        store.record_step_completion("task-001", "step-1", "步骤1", "A的步骤", {})

        # 验证隔离
        ctx_a = store.get_context("task-001")
        ctx_b = store.get_context("task-002")

        assert len(ctx_a.step_summaries) == 1
        assert len(ctx_b.step_summaries) == 0

    def test_to_prompt_format(self):
        """测试生成提示词格式"""
        store = TaskContextStore(backend="memory")
        store.start_task("task-001", "tenant-001", "search", "搜索曾德龙")
        store.record_step_completion("task-001", "step-1", "搜索", "完成", {"query": "曾德龙"})

        prompt = store.to_prompt("task-001")

        assert "搜索曾德龙" in prompt
        assert "搜索" in prompt
        assert "query: 曾德龙" in prompt
```

---

### MEM-005: 实现 EnterpriseMemoryRouter

**目标**: 实现记忆路由器，统一管理三层存储

**文件**: `src/openakita/memory/enterprise/router.py`

**后端单元测试用例**:
```python
# tests/memory/enterprise/test_router.py

class TestEnterpriseMemoryRouter:
    @pytest.fixture
    def router(self, tmp_path):
        config = EnterpriseMemoryConfig(
            rules_path=str(tmp_path / "rules.yaml"),
            context_backend="memory",
            skill_path=str(tmp_path / "skills.json"),
        )
        return EnterpriseMemoryRouter(config)

    def test_get_injection_context(self, router):
        """测试获取注入上下文"""
        router.start_task("task-001", "tenant-001", "search", "搜索曾德龙")
        router.record_step_completion("task-001", "step-1", "搜索", "完成", {})

        context = await router.get_injection_context("task-001", "search", "曾德龙是谁")

        assert "搜索曾德龙" in context
        assert "搜索" in context

    def test_context_without_task(self, router):
        """测试没有任务时返回空上下文"""
        context = await router.get_injection_context("nonexistent", "search", "query")
        # 应该返回系统规则，即使没有任务
        assert context is not None

    def test_task_lifecycle(self, router):
        """测试任务生命周期"""
        # 开始
        router.start_task("task-001", "tenant-001", "search", "搜索")

        # 更新
        router.record_step_completion("task-001", "step-1", "步骤1", "完成", {})

        # 结束
        router.end_task("task-001")

        # 验证清理
        context = await router.get_injection_context("task-001", "search", "query")
        # 任务已结束，不应包含任务上下文
```

---

### CTX-001: 定义 ContextBackend 协议

**文件**: `src/openakita/context/protocol.py`

```python
@runtime_checkable
class ContextBackend(Protocol):
    """Context 后端协议"""

    def build_context(self, task_id: str, session_id: str) -> tuple[str, list[dict]]:
        """构建完整上下文，返回 (system_prompt, messages)"""
        ...

    def add_message(self, session_id: str, role: str, content: str | list) -> None:
        """添加消息"""
        ...

    def get_stats(self, task_id: str, session_id: str) -> dict:
        """获取统计信息"""
        ...

    def clear_session(self, session_id: str) -> None:
        """清理会话"""
        ...
```

---

### CTX-005: 实现 EnterpriseContextManager

**文件**: `src/openakita/context/enterprise/manager.py`

**后端单元测试用例**:
```python
# tests/context/enterprise/test_manager.py

class TestEnterpriseContextManager:
    @pytest.fixture
    def manager(self):
        config = ContextConfig(
            max_conversation_rounds=20,
            max_task_summaries=20,
            max_task_variables=50,
        )
        manager = EnterpriseContextManager(config)
        manager.initialize(
            identity="我是企业助手",
            rules=["规则1", "规则2"],
            tools_manifest="工具列表"
        )
        return manager

    def test_initialize_system_context(self, manager):
        """测试初始化系统上下文"""
        assert manager.system_ctx is not None
        assert "企业助手" in manager.system_ctx.to_prompt()

    def test_task_lifecycle(self, manager):
        """测试任务生命周期"""
        # 开始任务
        manager.start_task("task-001", "tenant-001", "search", "搜索任务")

        # 更新
        manager.update_task_step("task-001", "步骤1", "完成搜索")

        # 验证
        ctx = manager.task_contexts.get("task-001")
        assert ctx is not None
        assert len(ctx.step_summaries) == 1

        # 结束
        manager.end_task("task-001")
        assert "task-001" not in manager.task_contexts

    def test_conversation_sliding_window(self, manager):
        """测试对话滑动窗口"""
        session_id = "session-001"

        # 添加 25 轮对话
        for i in range(25):
            manager.add_message(session_id, "user", f"用户消息{i}")
            manager.add_message(session_id, "assistant", f"助手回复{i}")

        conv_ctx = manager.conversation_contexts.get(session_id)
        rounds = conv_ctx._count_rounds()

        # 应该保留最近 20 轮
        assert rounds <= 20

    def test_build_full_context(self, manager):
        """测试构建完整上下文"""
        manager.start_task("task-001", "tenant-001", "search", "搜索")

        system_prompt, messages = manager.build_full_context("task-001", "session-001")

        # 验证系统提示包含各层
        assert "企业助手" in system_prompt  # System 层
        assert "搜索" in system_prompt  # Task 层

        # 验证消息
        assert isinstance(messages, list)

    def test_get_context_stats(self, manager):
        """测试获取上下文统计"""
        manager.start_task("task-001", "tenant-001", "search", "搜索")
        manager.add_message("session-001", "user", "测试消息")

        stats = manager.get_context_stats("task-001", "session-001")

        assert "system_tokens" in stats
        assert "task_tokens" in stats
        assert "conversation_tokens" in stats
        assert "conversation_rounds" in stats

    def test_tool_result_grouping(self, manager):
        """测试工具调用结果分组不被拆散"""
        session_id = "session-001"

        # 添加工具调用序列
        manager.add_message(session_id, "user", "帮我搜索")
        manager.add_message(session_id, "assistant", [
            {"type": "text", "text": "正在搜索..."},
            {"type": "tool_use", "id": "tool-1", "name": "search", "input": {}}
        ])
        manager.add_message(session_id, "tool", {"tool_call_id": "tool-1", "content": "搜索结果"})

        messages = manager.conversation_contexts[session_id].to_messages()

        # 验证 tool_use 和 tool_result 配对存在
        has_tool_use = any(
            any(isinstance(c, dict) and c.get("type") == "tool_use" for c in m.get("content", []))
            for m in messages if isinstance(m.get("content"), list)
        )
        assert has_tool_use
```

---

## 四、Chrome 插件端到端测试

### 4.1 测试环境准备

```bash
# 1. 启动后端服务
cd src/openakita
python -m openakita.server --config config/enterprise.yaml

# 2. 启动前端
cd webapps/seeagent-webui
pnpm dev

# 3. 打开 Chrome 插件测试工具
# 使用 Puppeteer 或 Playwright 进行自动化测试
```

### 4.2 测试用例定义

#### E2E-TC-001: Memory 系统基本功能

```typescript
// tests/e2e/memory-basic.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Memory System E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5174');
    // 切换到 Enterprise 模式
    await page.click('[data-testid="mode-selector"]');
    await page.click('[data-testid="enterprise-mode"]');
  });

  test('MEM-E2E-001: 任务上下文创建和显示', async ({ page }) => {
    // 1. 发送消息创建任务
    await page.fill('[data-testid="chat-input"]', '帮我搜索曾德龙是谁');
    await page.click('[data-testid="send-button"]');

    // 2. 等待响应开始
    await page.waitForSelector('[data-testid="step-card"]', { timeout: 30000 });

    // 3. 验证步骤显示
    const steps = await page.$$('[data-testid="step-card"]');
    expect(steps.length).toBeGreaterThan(0);

    // 4. 验证任务上下文已记录
    const response = await page.request.get('/api/memory/stats');
    const stats = await response.json();
    expect(stats.task_contexts).toBeGreaterThan(0);
  });

  test('MEM-E2E-002: 步骤记录和摘要', async ({ page }) => {
    // 1. 发送复杂任务
    await page.fill('[data-testid="chat-input"]', '帮我搜索曾德龙，然后写成PDF');
    await page.click('[data-testid="send-button"]');

    // 2. 等待完成
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 60000 });

    // 3. 验证步骤摘要
    const response = await page.request.get('/api/memory/task/latest');
    const task = await response.json();
    expect(task.step_summaries.length).toBeGreaterThan(1);
    expect(task.step_summaries[0]).toContain('搜索');
  });

  test('MEM-E2E-003: 系统规则注入', async ({ page }) => {
    // 1. 发送可能触发规则的请求
    await page.fill('[data-testid="chat-input"]', '帮我删除所有文件');
    await page.click('[data-testid="send-button"]');

    // 2. 等待响应
    await page.waitForSelector('[data-testid="ai-response"]', { timeout: 30000 });

    // 3. 验证规则生效（拒绝危险操作）
    const response = await page.locator('[data-testid="ai-response"]').textContent();
    expect(response).toMatch(/不能|拒绝|安全|风险/);
  });

  test('MEM-E2E-004: 多租户隔离', async ({ page }) => {
    // 1. 切换租户 A
    await page.click('[data-testid="tenant-selector"]');
    await page.click('[data-testid="tenant-A"]');

    // 2. 发送消息
    await page.fill('[data-testid="chat-input"]', '租户A的测试数据');
    await page.click('[data-testid="send-button"]');
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 30000 });

    // 3. 切换租户 B
    await page.click('[data-testid="tenant-selector"]');
    await page.click('[data-testid="tenant-B"]');

    // 4. 验证看不到租户 A 的数据
    const response = await page.request.get('/api/memory/task/latest');
    const task = await response.json();
    expect(task).toBeNull(); // 或者不包含租户 A 的数据
  });

  test('MEM-E2E-005: 任务结束清理', async ({ page }) => {
    // 1. 创建并完成任务
    await page.fill('[data-testid="chat-input"]', '测试任务清理');
    await page.click('[data-testid="send-button"]');
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 30000 });

    // 2. 获取任务 ID
    const taskId = await page.locator('[data-testid="task-id"]').textContent();

    // 3. 开始新任务（触发清理）
    await page.fill('[data-testid="chat-input"]', '新任务');
    await page.click('[data-testid="send-button"]');
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 30000 });

    // 4. 验证旧任务已清理
    const response = await page.request.get(`/api/memory/task/${taskId}`);
    expect(response.status()).toBe(404);
  });
});
```

#### E2E-TC-002: Context 系统基本功能

```typescript
// tests/e2e/context-basic.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Context System E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5174');
    await page.click('[data-testid="mode-selector"]');
    await page.click('[data-testid="enterprise-mode"]');
  });

  test('CTX-E2E-001: 滑动窗口裁剪', async ({ page }) => {
    // 1. 发送 25 轮对话
    for (let i = 0; i < 25; i++) {
      await page.fill('[data-testid="chat-input"]', `第${i + 1}轮对话`);
      await page.click('[data-testid="send-button"]');
      await page.waitForSelector(`text=第${i + 1}轮`, { timeout: 10000 });
    }

    // 2. 验证只保留 20 轮
    const response = await page.request.get('/api/context/stats');
    const stats = await response.json();
    expect(stats.conversation_rounds).toBeLessThanOrEqual(20);
  });

  test('CTX-E2E-002: 上下文性能测试', async ({ page }) => {
    // 1. 记录开始时间
    const startTime = Date.now();

    // 2. 发送消息
    await page.fill('[data-testid="chat-input"]', '性能测试');
    await page.click('[data-testid="send-button"]');

    // 3. 等待第一个响应
    await page.waitForSelector('[data-testid="ai-response"]', { timeout: 30000 });

    // 4. 验证上下文构建延迟 < 50ms
    const response = await page.request.get('/api/context/last-build-time');
    const data = await response.json();
    expect(data.build_time_ms).toBeLessThan(50);
  });

  test('CTX-E2E-003: 三层上下文组装', async ({ page }) => {
    // 1. 发送任务
    await page.fill('[data-testid="chat-input"]', '组装测试');
    await page.click('[data-testid="send-button"]');
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 30000 });

    // 2. 获取上下文内容
    const response = await page.request.get('/api/context/full');
    const context = await response.json();

    // 3. 验证三层存在
    expect(context.system_prompt).toContain('身份');  // System 层
    expect(context.system_prompt).toContain('规则');  // Rules 层
    expect(context.messages).toBeInstanceOf(Array);   // Conversation 层
  });

  test('CTX-E2E-004: 工具调用配对保护', async ({ page }) => {
    // 1. 发送需要工具调用的任务
    await page.fill('[data-testid="chat-input"]', '帮我搜索曾德龙');
    await page.click('[data-testid="send-button"]');
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 60000 });

    // 2. 获取消息列表
    const response = await page.request.get('/api/context/messages');
    const messages = await response.json();

    // 3. 验证 tool_use 和 tool_result 配对
    let toolUseCount = 0;
    let toolResultCount = 0;

    for (const msg of messages) {
      if (msg.role === 'assistant' && Array.isArray(msg.content)) {
        toolUseCount += msg.content.filter(c => c.type === 'tool_use').length;
      }
      if (msg.role === 'tool') {
        toolResultCount++;
      }
    }

    expect(toolUseCount).toBe(toolResultCount);
  });
});
```

#### E2E-TC-003: 完整流程测试

```typescript
// tests/e2e/full-flow.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Full Flow E2E Tests', () => {
  test('FULL-E2E-001: 复杂任务完整流程', async ({ page }) => {
    await page.goto('http://localhost:5174');
    await page.click('[data-testid="enterprise-mode"]');

    // 1. 发送复杂任务
    await page.fill('[data-testid="chat-input"]',
      '帮我搜索曾德龙是谁，整理成简介，然后生成PDF文件');
    await page.click('[data-testid="send-button"]');

    // 2. 等待步骤显示
    await page.waitForSelector('[data-testid="step-card"]', { timeout: 30000 });

    // 3. 验证步骤顺序
    const steps = await page.$$eval('[data-testid="step-title"]', els =>
      els.map(el => el.textContent)
    );

    expect(steps.length).toBeGreaterThanOrEqual(3);
    expect(steps[0]).toMatch(/搜索|查询/);
    expect(steps.some(s => s.includes('PDF') || s.includes('文件'))).toBe(true);

    // 4. 等待完成
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 120000 });

    // 5. 验证文件生成
    const artifacts = await page.$$('[data-testid="artifact-card"]');
    expect(artifacts.length).toBeGreaterThan(0);

    // 6. 验证任务上下文记录
    const memResponse = await page.request.get('/api/memory/task/latest');
    const task = await memResponse.json();
    expect(task.step_summaries.length).toBeGreaterThanOrEqual(3);

    // 7. 验证上下文统计
    const ctxResponse = await page.request.get('/api/context/stats');
    const stats = await ctxResponse.json();
    expect(stats.conversation_rounds).toBe(1);
    expect(stats.task_steps).toBeGreaterThanOrEqual(3);
  });

  test('FULL-E2E-002: 错误恢复流程', async ({ page }) => {
    await page.goto('http://localhost:5174');
    await page.click('[data-testid="enterprise-mode"]');

    // 1. 发送会失败的请求（模拟网络错误）
    await page.route('**/api/search', route => route.abort('failed'));

    await page.fill('[data-testid="chat-input"]', '帮我搜索测试数据');
    await page.click('[data-testid="send-button"]');

    // 2. 等待错误处理
    await page.waitForSelector('[data-testid="step-error"]', { timeout: 30000 });

    // 3. 验证错误记录
    const response = await page.request.get('/api/memory/task/latest');
    const task = await response.json();
    expect(task.errors.length).toBeGreaterThan(0);
    expect(task.errors[0].error_type).toBeDefined();

    // 4. 取消路由拦截，重试
    await page.unroute('**/api/search');

    // 5. 验证重试机制
    await page.click('[data-testid="retry-button"]');
    await page.waitForSelector('[data-testid="task-complete"]', { timeout: 60000 });
  });

  test('FULL-E2E-003: 性能基准测试', async ({ page }) => {
    await page.goto('http://localhost:5174');
    await page.click('[data-testid="enterprise-mode"]');

    const metrics: { name: string; duration: number }[] = [];

    // 测试 1: 首次响应时间
    const t1 = Date.now();
    await page.fill('[data-testid="chat-input"]', '测试1');
    await page.click('[data-testid="send-button"]');
    await page.waitForSelector('[data-testid="ai-response"]', { timeout: 30000 });
    metrics.push({ name: 'first_response', duration: Date.now() - t1 });

    // 测试 2: 上下文构建时间
    const ctxResponse = await page.request.get('/api/context/last-build-time');
    const ctxData = await ctxResponse.json();
    metrics.push({ name: 'context_build', duration: ctxData.build_time_ms });

    // 测试 3: Memory 操作时间
    const memResponse = await page.request.get('/api/memory/last-operation-time');
    const memData = await memResponse.json();
    metrics.push({ name: 'memory_operation', duration: memData.operation_time_ms });

    // 验证性能指标
    console.log('Performance Metrics:', metrics);

    for (const m of metrics) {
      if (m.name === 'context_build') {
        expect(m.duration).toBeLessThan(50); // 上下文构建 < 50ms
      }
      if (m.name === 'memory_operation') {
        expect(m.duration).toBeLessThan(100); // Memory 操作 < 100ms
      }
    }
  });
});
```

### 4.3 测试运行脚本

```bash
# scripts/run-e2e-tests.sh

#!/bin/bash

echo "=== Enterprise Memory & Context E2E Tests ==="

# 1. 启动后端
echo "Starting backend..."
cd src/openakita
python -m openakita.server --config config/enterprise-test.yaml &
BACKEND_PID=$!
cd ../..

# 2. 等待后端就绪
sleep 5

# 3. 启动前端
echo "Starting frontend..."
cd webapps/seeagent-webui
pnpm dev &
FRONTEND_PID=$!
cd ../..

# 4. 等待前端就绪
sleep 5

# 5. 运行 E2E 测试
echo "Running E2E tests..."
cd tests/e2e
npx playwright test --reporter=html

# 6. 收集结果
TEST_RESULT=$?

# 7. 清理
kill $BACKEND_PID
kill $FRONTEND_PID

# 8. 输出结果
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ All E2E tests passed!"
else
    echo "❌ E2E tests failed!"
    exit 1
fi
```

---

## 五、执行计划时间表

| 阶段 | 任务 ID | 预计时间 | 累计 |
|------|---------|---------|------|
| **第 1 天** | | | |
| 上午 | MEM-001, MEM-002 | 2h | 2h |
| 下午 | MEM-003, MEM-004 | 2h | 4h |
| **第 2 天** | | | |
| 上午 | MEM-005, MEM-006 | 2h | 6h |
| 下午 | MEM-007, MEM-008 | 2h | 8h |
| **第 3 天** | | | |
| 上午 | CTX-001, CTX-002, CTX-003 | 2h | 10h |
| 下午 | CTX-004, CTX-005 | 2h | 12h |
| **第 4 天** | | | |
| 上午 | CTX-006, CTX-007, CTX-008 | 2h | 14h |
| 下午 | E2E-001, E2E-002 | 2h | 16h |
| **第 5 天** | | | |
| 上午 | E2E-003, 联调测试 | 2h | 18h |
| 下午 | 文档更新, 代码清理 | 2h | 20h |

**总计**: 约 20 小时（5 个工作日）

---

## 六、验收检查清单

### 6.1 功能验收

- [ ] Memory 系统三层存储正常工作
- [ ] Context 系统三层架构正常工作
- [ ] 滑动窗口裁剪正常（≤20 轮）
- [ ] 任务结束自动清理
- [ ] 多租户隔离正确
- [ ] 系统规则正确注入

### 6.2 性能验收

- [ ] 上下文构建延迟 < 50ms
- [ ] Memory 操作延迟 < 100ms
- [ ] 无 LLM 调用用于压缩
- [ ] 内存占用 < 50MB（无 embedding 模型）

### 6.3 测试验收

- [ ] 后端单元测试全部通过
- [ ] Chrome 插件 E2E 测试全部通过
- [ ] 测试覆盖率 > 80%

### 6.4 文档验收

- [ ] API 文档更新
- [ ] 配置文档更新
- [ ] 迁移指南完成

---

*文档更新时间: 2026-02-23*
