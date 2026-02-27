# 任务清单 - 企业级可自我进化Agent改进

## Phase 1: 上下文管理改进 (12 个任务)

### 1.1 基础设施 (3 个任务)

#### TASK-001: 创建 context 模块基础设施
**预估时间**: 30分钟
**依赖**: 无
**输出文件**:
- `src/openakita/context/__init__.py`
- `src/openakita/context/interfaces.py`
- `src/openakita/context/exceptions.py`
- `src/openakita/context/config.py`

**验收标准**:
- [ ] `interfaces.py` 定义 `IContext`, `ICompressor` 抽象基类
- [ ] `exceptions.py` 定义 `ContextError`, `TokenBudgetExceeded` 异常
- [ ] `config.py` 定义 `TokenBudget`, `ContextConfig` 配置类
- [ ] 后端单元测试: `tests/test_context/test_001_infrastructure.py`
- [ ] 测试覆盖: 配置类序列化/反序列化，异常捕获

**测试用例**:
```python
# tests/test_context/test_001_infrastructure.py
def test_token_budget_defaults():
    budget = TokenBudget()
    assert budget.total == 128000
    assert budget.system_reserve == 16000

def test_context_error_inheritance():
    err = TokenBudgetExceeded("exceeded")
    assert isinstance(err, ContextError)
```

---

#### TASK-002: 实现 SystemContext (永久层)
**预估时间**: 45分钟
**依赖**: TASK-001
**输出文件**:
- `src/openakita/context/system_context.py`
- `tests/test_context/test_002_system_context.py`

**验收标准**:
- [ ] 实现 `SystemContext` dataclass
- [ ] 包含 `identity`, `rules`, `capabilities_manifest`, `policies` 字段
- [ ] 实现 `to_prompt()` 方法生成系统提示
- [ ] 实现 `refresh_capabilities()` 方法刷新能力清单
- [ ] 后端单元测试: 验证 prompt 生成格式

**测试用例**:
```python
def test_system_context_to_prompt():
    ctx = SystemContext(
        identity="AI Assistant",
        rules=["Be helpful", "Be honest"],
        capabilities_manifest="Tools: read, write"
    )
    prompt = ctx.to_prompt()
    assert "# 身份" in prompt
    assert "Be helpful" in prompt

def test_refresh_capabilities():
    ctx = SystemContext(identity="Test")
    ctx.refresh_capabilities("New capabilities")
    assert ctx.capabilities_manifest == "New capabilities"
```

---

#### TASK-003: 实现 TaskContext (任务层)
**预估时间**: 45分钟
**依赖**: TASK-001
**输出文件**:
- `src/openakita/context/task_context.py`
- `tests/test_context/test_003_task_context.py`

**验收标准**:
- [ ] 实现 `TaskContext` dataclass
- [ ] 包含 `task_id`, `tenant_id`, `task_description`, `variables` 字段
- [ ] 实现检查点机制 `save_checkpoint()`, `rollback()`
- [ ] 实现进度跟踪 `add_step_summary()`
- [ ] 后端单元测试: 验证检查点保存和回滚

**测试用例**:
```python
def test_task_context_checkpoint():
    ctx = TaskContext(task_id="t1", tenant_id="tenant1", task_description="Test")
    ctx.add_variables({"key": "value"})
    cp_id = ctx.save_checkpoint({"state": "initial"})

    ctx.add_variables({"key2": "value2"})
    assert ctx.variables["key2"] == "value2"

    state = ctx.rollback(cp_id)
    assert state["state"] == "initial"
    # 注意: rollback 不恢复 variables，只返回检查点状态

def test_step_progress():
    ctx = TaskContext(task_id="t1", tenant_id="t1", task_description="Test", total_steps=3)
    ctx.add_step_summary("step1", "done")
    assert ctx.completed_steps == 1
```

---

### 1.2 会话层与压缩 (3 个任务)

#### TASK-004: 实现 ConversationContext (会话层)
**预估时间**: 45分钟
**依赖**: TASK-001
**输出文件**:
- `src/openakita/context/conversation_context.py`
- `tests/test_context/test_004_conversation_context.py`

**验收标准**:
- [ ] 实现 `ConversationContext` dataclass
- [ ] 实现滑动窗口策略 `_apply_sliding_window()`
- [ ] 实现 Token 估算 `estimate_tokens()`
- [ ] 实现 `add_message()` 自动执行限制策略
- [ ] 后端单元测试: 验证滑动窗口行为

---

#### TASK-005: 实现 ContextCompressor (压缩器)
**预估时间**: 1小时
**依赖**: TASK-004
**输出文件**:
- `src/openakita/context/compressor.py`
- `tests/test_context/test_005_compressor.py`

**验收标准**:
- [ ] 实现 `ContextCompressor` 类
- [ ] 支持多种压缩策略: sliding_window, summary, priority
- [ ] 实现 `compress()` 方法返回压缩后的上下文
- [ ] 后端单元测试: 验证各策略效果

---

#### TASK-006: 实现 Token 预算控制器
**预估时间**: 45分钟
**依赖**: TASK-005
**输出文件**:
- `src/openakita/context/budget_controller.py`
- `tests/test_context/test_006_budget_controller.py`

**验收标准**:
- [ ] 实现 `BudgetController` 类
- [ ] 支持动态预算分配
- [ ] 实现预算检查 `check_budget()`, `allocate()`
- [ ] 后端单元测试: 验证预算计算和分配

---

### 1.3 编排器 (3 个任务)

#### TASK-007: 实现 ContextOrchestrator 基础版
**预估时间**: 1小时
**依赖**: TASK-002, TASK-003, TASK-004
**输出文件**:
- `src/openakita/context/orchestrator.py`
- `tests/test_context/test_007_orchestrator.py`

**验收标准**:
- [ ] 实现 `ContextOrchestrator` 类
- [ ] 实现 `create_task()`, `get_or_create_conversation()` 方法
- [ ] 实现 `build_context()` 组装三层上下文
- [ ] 后端单元测试: 验证上下文组装

---

#### TASK-008: 实现上下文优先级调度
**预估时间**: 45分钟
**依赖**: TASK-007
**输出文件**:
- 更新 `src/openakita/context/orchestrator.py`
- `tests/test_context/test_008_priority_scheduling.py`

**验收标准**:
- [ ] 实现优先级队列管理
- [ ] 当 Token 超限时按优先级裁剪
- [ ] 后端单元测试: 验证优先级行为

---

#### TASK-009: 集成到 Agent 初始化流程
**预估时间**: 1小时
**依赖**: TASK-007
**输出文件**:
- 更新 `src/openakita/core/agent.py`
- `tests/test_context/test_009_agent_integration.py`

**验收标准**:
- [ ] Agent 初始化时创建 ContextOrchestrator
- [ ] 系统提示通过 SystemContext 生成
- [ ] 后端单元测试: 验证 Agent 上下文初始化

---

### 1.4 集成测试 (3 个任务)

#### TASK-010: 后端集成测试 - 上下文切换
**预估时间**: 1小时
**依赖**: TASK-009
**输出文件**:
- `tests/integration/test_context_switching.py`

**验收标准**:
- [ ] 测试多任务上下文隔离
- [ ] 测试会话上下文滑动窗口
- [ ] 测试 Token 预算自动压缩

---

#### TASK-011: 前端测试 - 多轮对话上下文管理
**预估时间**: 1小时
**依赖**: TASK-010
**输出文件**:
- `tests/e2e/test_context_ui.py`

**验收标准**:
- [ ] Playwright 测试: 发送 20+ 轮对话
- [ ] 验证上下文不会无限增长
- [ ] 验证重要上下文被保留

---

#### TASK-012: Phase 1 总结与文档
**预估时间**: 30分钟
**依赖**: TASK-011
**输出文件**:
- `docs/refactor/context_layer_complete.md`

**验收标准**:
- [ ] 更新架构文档
- [ ] 记录性能基准数据
- [ ] 记录已知问题和改进方向

---

## Phase 2: 能力层改进 (10 个任务)

### 2.1 类型定义与注册表 (3 个任务)

#### TASK-101: 定义 Capability 类型系统
**预估时间**: 45分钟
**依赖**: Phase 1 完成
**输出文件**:
- `src/openakita/capability/__init__.py`
- `src/openakita/capability/types.py`
- `tests/test_capability/test_101_types.py`

**验收标准**:
- [ ] 实现 `CapabilityType` 枚举
- [ ] 实现 `CapabilityMeta` dataclass
- [ ] 后端单元测试: 验证类型系统完整性

---

#### TASK-102: 实现 CapabilityRegistry 核心
**预估时间**: 1小时
**依赖**: TASK-101
**输出文件**:
- `src/openakita/capability/registry.py`
- `tests/test_capability/test_102_registry.py`

**验收标准**:
- [ ] 实现 `register()`, `unregister()`, `get()`, `search()` 方法
- [ ] 实现分类索引 `list_by_type()`, `list_by_tag()`
- [ ] 实现使用统计 `record_usage()`
- [ ] 后端单元测试: 验证注册表 CRUD 操作

---

#### TASK-103: 实现能力清单生成器
**预估时间**: 45分钟
**依赖**: TASK-102
**输出文件**:
- 更新 `src/openakita/capability/registry.py`
- `tests/test_capability/test_103_manifest.py`

**验收标准**:
- [ ] 实现 `generate_manifest()` 生成 Markdown 格式清单
- [ ] 清单可注入到 SystemPrompt
- [ ] 后端单元测试: 验证清单格式

---

### 2.2 适配器实现 (4 个任务)

#### TASK-104: 实现 CapabilityAdapter 基类
**预估时间**: 45分钟
**依赖**: TASK-101
**输出文件**:
- `src/openakita/capability/adapters/__init__.py`
- `src/openakita/capability/adapters/base.py`
- `tests/test_capability/test_104_adapter_base.py`

**验收标准**:
- [ ] 定义 `CapabilityAdapter` 抽象基类
- [ ] 定义 `load()`, `execute()` 抽象方法
- [ ] 后端单元测试: 验证接口契约

---

#### TASK-105: 实现 ToolAdapter
**预估时间**: 1小时
**依赖**: TASK-104
**输出文件**:
- `src/openakita/capability/adapters/tool_adapter.py`
- `tests/test_capability/test_105_tool_adapter.py`

**验收标准**:
- [ ] 将现有 ToolCatalog 转换为 CapabilityMeta
- [ ] 集成 ToolExecutor 执行工具
- [ ] 后端单元测试: 验证工具加载和执行

---

#### TASK-106: 实现 SkillAdapter
**预估时间**: 1小时
**依赖**: TASK-104
**输出文件**:
- `src/openakita/capability/adapters/skill_adapter.py`
- `tests/test_capability/test_106_skill_adapter.py`

**验收标准**:
- [ ] 从 SKILL.md 解析能力元数据
- [ ] 集成 SkillManager 执行技能
- [ ] 后端单元测试: 验证技能加载和执行

---

#### TASK-107: 实现 MCPAdapter
**预估时间**: 1小时
**依赖**: TASK-104
**输出文件**:
- `src/openakita/capability/adapters/mcp_adapter.py`
- `tests/test_capability/test_107_mcp_adapter.py`

**验收标准**:
- [ ] 从 MCP Server 加载工具列表
- [ ] 实现 MCP 工具调用
- [ ] 后端单元测试: 使用 Mock MCP Server

---

### 2.3 集成与测试 (3 个任务)

#### TASK-108: 实现统一执行器
**预估时间**: 1小时
**依赖**: TASK-105, TASK-106, TASK-107
**输出文件**:
- `src/openakita/capability/executor.py`
- `tests/test_capability/test_108_executor.py`

**验收标准**:
- [ ] 实现 `CapabilityExecutor` 统一执行入口
- [ ] 支持路由到正确的适配器
- [ ] 后端单元测试: 验证路由逻辑

---

#### TASK-109: 集成到 Agent
**预估时间**: 1.5小时
**依赖**: TASK-108
**输出文件**:
- 更新 `src/openakita/core/agent.py`
- `tests/test_capability/test_109_agent_integration.py`

**验收标准**:
- [ ] Agent 使用 CapabilityRegistry 替代原有工具管理
- [ ] 动态加载能力到 SystemContext
- [ ] 后端单元测试: 验证能力发现和调用

---

#### TASK-110: Phase 2 总结与文档
**预估时间**: 30分钟
**依赖**: TASK-109
**输出文件**:
- `docs/refactor/capability_layer_complete.md`

**验收标准**:
- [ ] 更新架构文档
- [ ] 记录适配器模式使用
- [ ] 记录性能影响

---

## Phase 3: 自我进化机制 (8 个任务)

### 3.1 经验存储 (3 个任务)

#### TASK-201: 实现 ExecutionTrace 数据模型
**预估时间**: 45分钟
**依赖**: Phase 2 完成
**输出文件**:
- `src/openakita/evolution/__init__.py`
- `src/openakita/evolution/models.py`
- `tests/test_evolution/test_201_models.py`

**验收标准**:
- [ ] 实现 `ExecutionTrace` dataclass
- [ ] 实现 `SuccessPattern` dataclass
- [ ] 实现 `Feedback` dataclass
- [ ] 后端单元测试: 验证数据模型

---

#### TASK-202: 实现 ExperienceStore 核心存储
**预估时间**: 1.5小时
**依赖**: TASK-201
**输出文件**:
- `src/openakita/evolution/experience_store.py`
- `tests/test_evolution/test_202_experience_store.py`

**验收标准**:
- [ ] 实现 `record_trace()` 记录执行轨迹
- [ ] 实现 `record_feedback()` 记录用户反馈
- [ ] 实现持久化存储
- [ ] 后端单元测试: 验证存储和检索

---

#### TASK-203: 实现模式提取器
**预估时间**: 1小时
**依赖**: TASK-202
**输出文件**:
- `src/openakita/evolution/pattern_extractor.py`
- `tests/test_evolution/test_203_pattern_extractor.py`

**验收标准**:
- [ ] 实现 `extract_patterns()` 从轨迹提取成功模式
- [ ] 支持工具序列模式、工作流模式提取
- [ ] 后端单元测试: 验证模式提取准确性

---

### 3.2 技能进化器 (3 个任务)

#### TASK-204: 实现 EvolutionProposal 生成器
**预估时间**: 1小时
**依赖**: TASK-203
**输出文件**:
- `src/openakita/evolution/proposal_generator.py`
- `tests/test_evolution/test_204_proposal_generator.py`

**验收标准**:
- [ ] 实现 `EvolutionProposal` 数据模型
- [ ] 实现缺失能力检测
- [ ] 实现优化机会检测
- [ ] 后端单元测试: 验证提案生成

---

#### TASK-205: 实现 SkillEvolver 核心逻辑
**预估时间**: 1.5小时
**依赖**: TASK-204
**输出文件**:
- `src/openakita/evolution/skill_evolver.py`
- `tests/test_evolution/test_205_skill_evolver.py`

**验收标准**:
- [ ] 实现 `analyze_and_propose()` 分析并生成进化提案
- [ ] 实现 `apply_proposal()` 应用提案
- [ ] 后端单元测试: 验证进化逻辑

---

#### TASK-206: 实现进化编排器
**预估时间**: 1小时
**依赖**: TASK-205
**输出文件**:
- `src/openakita/evolution/orchestrator.py`
- `tests/test_evolution/test_206_evolution_orchestrator.py`

**验收标准**:
- [ ] 实现进化闭环: 收集 → 分析 → 生成 → 验证
- [ ] 支持定时触发和手动触发
- [ ] 后端单元测试: 验证闭环流程

---

### 3.3 集成测试 (2 个任务)

#### TASK-207: 集成到 Agent 执行流程
**预估时间**: 1.5小时
**依赖**: TASK-206
**输出文件**:
- 更新 `src/openakita/core/agent.py`
- 更新 `src/openakita/core/reasoning_engine.py`
- `tests/test_evolution/test_207_agent_integration.py`

**验收标准**:
- [ ] 任务完成后自动记录执行轨迹
- [ ] 支持用户反馈收集
- [ ] 后端单元测试: 验证自动记录

---

#### TASK-208: Phase 3 总结与文档
**预估时间**: 30分钟
**依赖**: TASK-207
**输出文件**:
- `docs/refactor/evolution_layer_complete.md`

**验收标准**:
- [ ] 更新架构文档
- [ ] 记录进化闭环效果
- [ ] 记录已知限制

---

## Phase 4: 集成与测试 (6 个任务)

### 4.1 端到端测试 (4 个任务)

#### TASK-301: 上下文管理端到端测试
**预估时间**: 1.5小时
**依赖**: Phase 1-3 完成
**输出文件**:
- `tests/e2e/test_e2e_context.py`

**验收标准**:
- [ ] Playwright 测试: 完整对话流程
- [ ] 验证上下文压缩行为
- [ ] 验证任务上下文隔离

---

#### TASK-302: 能力发现与调用端到端测试
**预估时间**: 1.5小时
**依赖**: TASK-301
**输出文件**:
- `tests/e2e/test_e2e_capability.py`

**验收标准**:
- [ ] Playwright 测试: 工具调用
- [ ] 验证动态能力加载
- [ ] 验证能力清单更新

---

#### TASK-303: 自我进化端到端测试
**预估时间**: 2小时
**依赖**: TASK-302
**输出文件**:
- `tests/e2e/test_e2e_evolution.py`

**验收标准**:
- [ ] Playwright 测试: 完整任务执行
- [ ] 验证轨迹记录
- [ ] 验证模式提取
- [ ] 验证进化提案生成

---

#### TASK-304: 性能基准测试
**预估时间**: 1.5小时
**依赖**: TASK-303
**输出文件**:
- `tests/benchmark/test_performance.py`
- `docs/refactor/performance_benchmark.md`

**验收标准**:
- [ ] 测量上下文构建延迟
- [ ] 测量能力查找延迟
- [ ] 测量进化分析延迟
- [ ] 记录基准数据

---

### 4.2 文档与清理 (2 个任务)

#### TASK-305: 完整架构文档
**预估时间**: 2小时
**依赖**: TASK-304
**输出文件**:
- `docs/architecture/enterprise_agent.md`
- `docs/architecture/context_layer.md`
- `docs/architecture/capability_layer.md`
- `docs/architecture/evolution_layer.md`

**验收标准**:
- [ ] 完整架构图
- [ ] 模块依赖图
- [ ] API 文档
- [ ] 使用示例

---

#### TASK-306: 最终清理与发布
**预估时间**: 1小时
**依赖**: TASK-305
**输出文件**:
- 更新 `CHANGELOG.md`
- 更新 `README.md`

**验收标准**:
- [ ] 所有测试通过
- [ ] 覆盖率达标
- [ ] 文档完整
- [ ] 准备发布

---

## 测试矩阵

| Phase | 后端单元测试 | 后端集成测试 | 前端 Playwright 测试 |
|-------|-------------|-------------|---------------------|
| 1     | 10 个       | 1 个        | 1 个                |
| 2     | 8 个        | 1 个        | 0 个                |
| 3     | 7 个        | 1 个        | 0 个                |
| 4     | 0 个        | 3 个        | 1 个                |
| **总计** | **25 个** | **6 个** | **2 个** |

## 风险缓解措施

1. **每个任务完成后立即运行测试**
   - 后端: `pytest tests/test_context/`
   - 前端: `pytest tests/e2e/ --playwright`

2. **每日进度检查**
   - 更新 `progress.txt`
   - 记录阻塞问题

3. **回归测试**
   - 每个 Phase 完成后运行全量测试
   - 确保现有功能不受影响

4. **性能监控**
   - 每个 Phase 完成后进行性能基准测试
   - 确保无性能退化