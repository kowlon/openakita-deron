# 企业级可自我进化Agent改进方案

## 概述

本文档基于对 OpenAkita-Main项目的深度分析，提出一个企业级可自我进化 Agent 的改进方案。重点聚焦于：
1. **上下文管理** - 分层架构、生命周期管理、Token 预算控制
2. **自我进化机制** - 技能学习、知识沉淀、能力迭代

---

## 一、现状分析

### 1.1 现有架构优势

| 模块 | 现状 | 评价 |
|------|------|------|
| Agent 核心 | Ralph 循环 + ReAct 推理引擎 | ✅ 成熟稳定 |
| 上下文管理 | EnterpriseContextManager 三层架构 | ⚠️ 已有基础，但集成不完整 |
| 技能系统 | SKILL.md 规范 + SkillManager | ✅ 设计优秀 |
| MCP 集成 | MCPClient 标准协议 | ✅ 可扩展 |
| 记忆系统 | Vector Memory + MEMORY.md | ⚠️ 需强化结构化 |
| 自进化 | SkillGenerator + LogAnalyzer | ⚠️ 功能初级，缺乏闭环 |

### 1.2 核心问题

```
┌─────────────────────────────────────────────────────────────────┐
│                      现有架构问题诊断                              │
├─────────────────────────────────────────────────────────────────┤
│  1. 上下文管理                                                   │
│     - EnterpriseContextManager 未被 Agent 完全采用              │
│     - Token 预算分配缺乏动态调整                                 │
│     - 任务间上下文隔离不彻底                                     │
│                                                                 │
│  2. 工具/技能/MCP 集成                                           │
│     - ToolCatalog、SkillCatalog、MCPManager 各自独立             │
│     - 缺乏统一的能力注册与发现机制                               │
│     - 动态加载/卸载机制不完善                                    │
│                                                                 │
│  3. 自我进化                                                     │
│     - 缺乏结构化的学习反馈闭环                                   │
│     - 知识沉淀粒度粗（仅 MEMORY.md）                             │
│     - 无能力评估与迭代机制                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、改进方案总览

### 2.1 架构蓝图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Enterprise Agent Architecture                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Agent Core (协调层)                           │   │
│  │  ┌───────────┐ ┌───────────────┐ ┌─────────────┐ ┌───────────────┐ │   │
│  │  │   Ralph   │ │ ReasoningEngine│ │  Interrupt  │ │  Response     │ │   │
│  │  │   Loop    │ │   (ReAct)     │ │  Manager    │ │  Handler      │ │   │
│  │  └───────────┘ └───────────────┘ └─────────────┘ └───────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                     Context Layer (上下文层)                           │ │
│  │                                                                        │ │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐  │ │
│  │  │  SystemContext  │ │   TaskContext    │ │  ConversationContext    │  │ │
│  │  │   (永久层)       │ │   (任务层)       │ │     (会话层)            │  │ │
│  │  │  - Identity     │ │  - Goal          │ │  - Sliding Window       │  │ │
│  │  │  - Rules        │ │  - Steps         │ │  - Summary Compression  │  │ │
│  │  │  - Capabilities │ │  - Variables     │ │  - Token Budget         │  │ │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │              ContextOrchestrator (统一编排器)                    │  │ │
│  │  │  - Token 预算动态分配                                            │  │ │
│  │  │  - 上下文优先级调度                                              │  │ │
│  │  │  - 压缩策略选择                                                  │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   Capability Layer (能力层)                           │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                CapabilityRegistry (统一能力注册表)                │ │ │
│  │  │  - Tools  ──────┐                                                │ │ │
│  │  │  - Skills ──────┼──► Unified Interface ◄── MCP Protocol          │ │ │
│  │  │  - MCP Tools ──┘                                                │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                        │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────────────────────┐│ │
│  │  │  ToolLoader   │ │ SkillLoader   │ │      MCPConnector            ││ │
│  │  │  (动态加载)    │ │ (SKILL.md)   │ │    (协议适配器)               ││ │
│  │  └───────────────┘ └───────────────┘ └───────────────────────────────┘│ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    Evolution Layer (进化层)                           │ │
│  │                                                                        │ │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐  │ │
│  │  │  ExperienceStore │ │  SkillEvolver   │ │   KnowledgeDistiller    │  │ │
│  │  │  (经验存储)      │ │  (技能进化)      │ │   (知识蒸馏)            │  │ │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │                   EvolutionOrchestrator                         │  │ │
│  │  │  - 反馈收集 → 经验沉淀 → 能力迭代 → 效果验证                      │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

| 原则 | 说明 | 实现方式 |
|------|------|----------|
| **高内聚** | 每个模块职责单一明确 | 单一职责原则，模块边界清晰 |
| **低耦合** | 模块间通过接口通信 | 依赖注入、事件驱动、适配器模式 |
| **可扩展** | 新能力即插即用 | 插件化架构、CapabilityRegistry |
| **可进化** | 从经验中持续学习 | 反馈闭环、知识蒸馏 |

---

## 三、上下文管理改进方案

### 3.1 分层上下文架构

#### 3.1.1 SystemContext (永久层)

```python
# src/openakita/context/system_context.py

@dataclass
class SystemContext:
    """
    系统上下文 - 永久层

    特点：
    - 启动时初始化一次
    - 身份、规则、能力清单
    - Token 预算固定或仅手动调整
    """
    identity: str                    # Agent 身份 (来自 SOUL.md)
    rules: list[str]                 # 行为规则 (来自 AGENT.md)
    capabilities_manifest: str       # 能力清单 (Tools + Skills + MCP)
    policies: list[str]              # 策略约束

    # Token 预算
    max_tokens: int = 4000
    _compiled_prompt: str = ""

    def to_prompt(self) -> str:
        """生成系统提示"""
        if not self._compiled_prompt:
            self._compile()
        return self._compiled_prompt

    def refresh_capabilities(self, manifest: str) -> None:
        """刷新能力清单（安装新技能时调用）"""
        self.capabilities_manifest = manifest
        self._compiled_prompt = ""  # 清除缓存

    def _compile(self) -> None:
        """编译系统提示"""
        parts = [
            f"# 身份\n{self.identity}",
            f"# 规则\n" + "\n".join(f"- {r}" for r in self.rules),
            f"# 能力\n{self.capabilities_manifest}",
        ]
        if self.policies:
            parts.append(f"# 策略\n" + "\n".join(f"- {p}" for p in self.policies))
        self._compiled_prompt = "\n\n".join(parts)
```

#### 3.1.2 TaskContext (任务层)

```python
# src/openakita/context/task_context.py

@dataclass
class TaskContext:
    """
    任务上下文 - 任务生命周期层

    特点：
    - 随任务创建/销毁
    - 目标、进度、变量
    - 支持检查点/回滚
    """
    task_id: str
    tenant_id: str                    # 多租户隔离
    task_type: str                    # 任务类型
    task_description: str             # 任务目标

    # 进度跟踪
    total_steps: int = 0
    completed_steps: int = 0
    step_summaries: list[str] = field(default_factory=list)

    # 变量存储
    variables: dict[str, Any] = field(default_factory=dict)

    # 检查点
    checkpoints: list[dict] = field(default_factory=list)

    # Token 预算
    max_tokens: int = 2000

    def add_step_summary(self, step_name: str, summary: str) -> None:
        """添加步骤摘要"""
        entry = f"[{self.completed_steps + 1}/{self.total_steps or '?'}] {step_name}: {summary}"
        self.step_summaries.append(entry)
        self.completed_steps += 1

    def add_variables(self, vars: dict) -> None:
        """添加任务变量"""
        self.variables.update(vars)

    def save_checkpoint(self, state: dict) -> str:
        """保存检查点"""
        checkpoint_id = f"cp_{len(self.checkpoints)}"
        self.checkpoints.append({
            "id": checkpoint_id,
            "state": state,
            "timestamp": datetime.now().isoformat(),
        })
        return checkpoint_id

    def rollback(self, checkpoint_id: str) -> dict | None:
        """回滚到检查点"""
        for cp in self.checkpoints:
            if cp["id"] == checkpoint_id:
                return cp["state"]
        return None

    def to_prompt(self) -> str:
        """生成任务提示"""
        parts = [f"# 任务目标\n{self.task_description}"]

        if self.step_summaries:
            parts.append("# 已完成步骤\n" + "\n".join(self.step_summaries))

        if self.variables:
            parts.append("# 关键变量\n" + self._format_variables())

        return "\n\n".join(parts)

    def _format_variables(self) -> str:
        """格式化变量"""
        lines = []
        for k, v in self.variables.items():
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + "..."
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)
```

#### 3.1.3 ConversationContext (会话层)

```python
# src/openakita/context/conversation_context.py

@dataclass
class ConversationContext:
    """
    会话上下文 - 滑动窗口层

    特点：
    - 消息历史滑动窗口
    - 支持 Token 预算压缩
    - 支持摘要压缩
    """
    max_rounds: int = 20              # 最大轮数
    max_tokens: int = 8000           # 最大 Token 预算

    messages: list[Message] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)  # 压缩摘要

    # 压缩策略
    compression_strategy: str = "sliding_window"  # or "summary"

    def add_message(self, role: str, content: str | list) -> None:
        """添加消息"""
        self.messages.append(Message(role=role, content=content))
        self._enforce_limits()

    def _enforce_limits(self) -> None:
        """执行限制策略"""
        if self.compression_strategy == "sliding_window":
            self._apply_sliding_window()
        else:
            self._apply_summary_compression()

    def _apply_sliding_window(self) -> None:
        """滑动窗口策略"""
        while len(self.messages) > self.max_rounds * 2:
            self.messages.pop(0)

    def _apply_summary_compression(self) -> None:
        """摘要压缩策略 - 需要LLM"""
        # 调用 LLM 生成摘要
        pass

    def estimate_tokens(self) -> int:
        """估算 Token 数"""
        total = 0
        for msg in self.messages:
            if isinstance(msg.content, str):
                total += len(msg.content) // 4  # 粗略估算
            else:
                for block in msg.content:
                    if isinstance(block, dict) and "text" in block:
                        total += len(block["text"]) // 4
        return total

    def to_messages(self) -> list[dict]:
        """转换为 API 消息格式"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
```

### 3.2 ContextOrchestrator (上下文编排器)

```python
# src/openakita/context/orchestrator.py

@dataclass
class TokenBudget:
    """Token 预算配置"""
    total: int = 128000              # 总预算 (Claude 3.5 Sonnet)
    system_reserve: int = 16000      # 系统层预留
    task_reserve: int = 4000         # 任务层预留
    conversation_reserve: int = 80000  # 会话层预留
    response_reserve: int = 16000    # 响应预留
    buffer: int = 12000              # 缓冲区


class ContextOrchestrator:
    """
    上下文编排器 - 统一管理上下文组装

    职责：
    - 协调三层上下文
    - 动态 Token 预算分配
    - 压缩策略选择
    - 优先级调度
    """

    def __init__(
        self,
        system_ctx: SystemContext,
        budget: TokenBudget | None = None,
    ):
        self.system_ctx = system_ctx
        self.budget = budget or TokenBudget()

        self.task_contexts: dict[str, TaskContext] = {}
        self.conversation_contexts: dict[str, ConversationContext] = {}

        # 压缩器
        self._compressor: ContextCompressor | None = None

    def create_task(
        self,
        task_id: str,
        tenant_id: str,
        description: str,
        **kwargs,
    ) -> TaskContext:
        """创建任务上下文"""
        ctx = TaskContext(
            task_id=task_id,
            tenant_id=tenant_id,
            task_description=description,
            **kwargs,
        )
        self.task_contexts[task_id] = ctx
        return ctx

    def get_or_create_conversation(self, session_id: str) -> ConversationContext:
        """获取或创建会话上下文"""
        if session_id not in self.conversation_contexts:
            self.conversation_contexts[session_id] = ConversationContext(
                max_tokens=self.budget.conversation_reserve,
            )
        return self.conversation_contexts[session_id]

    def build_context(
        self,
        task_id: str,
        session_id: str,
    ) -> tuple[str, list[dict]]:
        """
        构建完整上下文

        返回:
            (system_prompt, messages)
        """
        # 1. 系统层
        system_prompt = self.system_ctx.to_prompt()
        system_tokens = self._estimate_tokens(system_prompt)

        # 2. 任务层
        task_ctx = self.task_contexts.get(task_id)
        if task_ctx:
            task_prompt = task_ctx.to_prompt()
            system_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        # 3. 会话层
        conv_ctx = self.conversation_contexts.get(session_id)
        messages = conv_ctx.to_messages() if conv_ctx else []

        # 4. Token 预算检查
        total_estimated = self._estimate_tokens(system_prompt)
        for msg in messages:
            total_estimated += self._estimate_message_tokens(msg)

        # 5. 如果超预算，执行压缩
        available = self.budget.total - self.budget.response_reserve - self.budget.buffer
        if total_estimated > available:
            system_prompt, messages = self._compress(
                system_prompt, messages, available
            )

        return system_prompt, messages

    def _compress(
        self,
        system_prompt: str,
        messages: list[dict],
        target: int,
    ) -> tuple[str, list[dict]]:
        """执行上下文压缩"""
        if self._compressor:
            return self._compressor.compress(system_prompt, messages, target)

        # 默认：简化策略
        # 1. 优先保留系统提示
        # 2. 截断会话历史
        current = self._estimate_tokens(system_prompt)
        remaining = target - current

        truncated_messages = []
        for msg in reversed(messages):  # 从最新开始
            msg_tokens = self._estimate_message_tokens(msg)
            if remaining >= msg_tokens:
                truncated_messages.insert(0, msg)
                remaining -= msg_tokens
            else:
                break

        return system_prompt, truncated_messages

    def _estimate_tokens(self, text: str) -> int:
        """估算文本 Token 数"""
        # 使用 tiktoken 或简化估算
        return len(text) // 4

    def _estimate_message_tokens(self, msg: dict) -> int:
        """估算消息 Token 数"""
        content = msg.get("content", "")
        if isinstance(content, str):
            return len(content) // 4 + 4  # 加上角色开销
        return 100  # 多模态内容估算
```

### 3.3 模块依赖关系

```
context/
├── __init__.py
├── config.py                 # ContextConfig, TokenBudget
├── system_context.py         # SystemContext (永久层)
├── task_context.py           # TaskContext (任务层)
├── conversation_context.py   # ConversationContext (会话层)
├── orchestrator.py           # ContextOrchestrator (编排器)
├── compressor.py             # ContextCompressor (压缩策略)
├── exceptions.py             # ContextError 等异常
└── interfaces.py            # 抽象接口定义
```

```
依赖关系 (从底层到高层):

interfaces.py (接口定义)
    ↑
config.py, exceptions.py
    ↑
system_context.py, task_context.py, conversation_context.py
    ↑
compressor.py
    ↑
orchestrator.py (统一入口)
```

---

## 四、能力层改进方案

### 4.1 统一能力注册表

```python
# src/openakita/capability/registry.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine


class CapabilityType(Enum):
    """能力类型"""
    TOOL = "tool"           # 本地工具
    SKILL = "skill"         # SKILL.md 技能
    MCP = "mcp"             # MCP 远程工具
    HYBRID = "hybrid"       # 混合能力


@dataclass
class CapabilityMeta:
    """能力元数据"""
    name: str                           # 能力名称
    type: CapabilityType                # 能力类型
    description: str                    # 描述
    input_schema: dict                  # 输入 Schema
    output_schema: dict | None = None   # 输出 Schema

    # 元信息
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)

    # 执行信息
    handler: str = ""                    # 处理器路径
    priority: int = 100                  # 优先级
    requires_confirmation: bool = False  # 是否需要确认
    timeout: int = 300                   # 超时秒数

    # 统计信息
    call_count: int = 0
    success_count: int = 0
    avg_latency_ms: float = 0.0


class CapabilityRegistry:
    """
    统一能力注册表

    职责：
    - 统一管理 Tool/Skill/MCP 能力
    - 能力发现与路由
    - 动态加载/卸载
    - 使用统计
    """

    def __init__(self):
        self._capabilities: dict[str, CapabilityMeta] = {}
        self._handlers: dict[str, Callable] = {}
        self._categories: dict[str, set[str]] = {}  # 分类索引

    def register(
        self,
        capability: CapabilityMeta,
        handler: Callable,
    ) -> None:
        """注册能力"""
        self._capabilities[capability.name] = capability
        self._handlers[capability.name] = handler

        # 更新分类索引
        for tag in capability.tags:
            if tag not in self._categories:
                self._categories[tag] = set()
            self._categories[tag].add(capability.name)

    def unregister(self, name: str) -> bool:
        """注销能力"""
        if name in self._capabilities:
            cap = self._capabilities.pop(name)
            self._handlers.pop(name, None)
            # 更新分类索引
            for tag in cap.tags:
                self._categories.get(tag, set()).discard(name)
            return True
        return False

    def get(self, name: str) -> CapabilityMeta | None:
        """获取能力元数据"""
        return self._capabilities.get(name)

    def get_handler(self, name: str) -> Callable | None:
        """获取能力处理器"""
        return self._handlers.get(name)

    def list_by_type(self, cap_type: CapabilityType) -> list[CapabilityMeta]:
        """按类型列出能力"""
        return [
            cap for cap in self._capabilities.values()
            if cap.type == cap_type
        ]

    def list_by_tag(self, tag: str) -> list[CapabilityMeta]:
        """按标签列出能力"""
        names = self._categories.get(tag, set())
        return [self._capabilities[n] for n in names if n in self._capabilities]

    def search(self, query: str) -> list[CapabilityMeta]:
        """搜索能力"""
        query = query.lower()
        return [
            cap for cap in self._capabilities.values()
            if query in cap.name.lower() or query in cap.description.lower()
        ]

    def generate_manifest(self) -> str:
        """生成能力清单 (注入到 SystemPrompt)"""
        lines = ["## 可用能力\n"]

        # 按类型分组
        for cap_type in CapabilityType:
            caps = self.list_by_type(cap_type)
            if not caps:
                continue

            lines.append(f"### {cap_type.value.upper()}\n")
            for cap in sorted(caps, key=lambda x: x.priority):
                lines.append(f"- **{cap.name}**: {cap.description}\n")

        return "".join(lines)

    def record_usage(
        self,
        name: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """记录使用统计"""
        cap = self._capabilities.get(name)
        if not cap:
            return

        cap.call_count += 1
        if success:
            cap.success_count += 1
        # 滚动平均延迟
        cap.avg_latency_ms = (
            cap.avg_latency_ms * (cap.call_count - 1) + latency_ms
        ) / cap.call_count
```

### 4.2 能力适配器

```python
# src/openakita/capability/adapters.py

class CapabilityAdapter(ABC):
    """能力适配器基类"""

    @abstractmethod
    async def load(self, source: str) -> list[CapabilityMeta]:
        """从源加载能力"""
        pass

    @abstractmethod
    async def execute(
        self,
        capability: CapabilityMeta,
        params: dict,
    ) -> Any:
        """执行能力"""
        pass


class ToolAdapter(CapabilityAdapter):
    """本地工具适配器"""

    def __init__(self, tool_executor):
        self._executor = tool_executor

    async def load(self, source: str) -> list[CapabilityMeta]:
        """从 ToolCatalog 加载"""
        # 转换 ToolCatalog 格式
        pass

    async def execute(self, capability: CapabilityMeta, params: dict) -> Any:
        """执行工具"""
        return await self._executor.execute_tool(capability.name, params)


class SkillAdapter(CapabilityAdapter):
    """SKILL.md 技能适配器"""

    def __init__(self, skill_manager):
        self._manager = skill_manager

    async def load(self, source: str) -> list[CapabilityMeta]:
        """从 SkillRegistry 加载"""
        pass

    async def execute(self, capability: CapabilityMeta, params: dict) -> Any:
        """执行技能"""
        return await self._manager.execute(capability.name, params)


class MCPAdapter(CapabilityAdapter):
    """MCP 工具适配器"""

    def __init__(self, mcp_client):
        self._client = mcp_client

    async def load(self, source: str) -> list[CapabilityMeta]:
        """从 MCP Server 加载工具列表"""
        pass

    async def execute(self, capability: CapabilityMeta, params: dict) -> Any:
        """调用 MCP 工具"""
        return await self._client.call_tool(capability.name, params)
```

### 4.3 能力层目录结构

```
capability/
├── __init__.py
├── registry.py          # CapabilityRegistry (核心)
├── types.py             # CapabilityType, CapabilityMeta
├── adapters/
│   ├── __init__.py
│   ├── base.py          # CapabilityAdapter 基类
│   ├── tool_adapter.py  # Tool 适配器
│   ├── skill_adapter.py # Skill 适配器
│   └── mcp_adapter.py   # MCP 适配器
├── loader.py            # 动态加载器
├── executor.py          # 统一执行器
└── validator.py         # Schema 验证器
```

---

## 五、自我进化机制设计

### 5.1 进化闭环架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Evolution Closed Loop                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌───────────┐      ┌───────────┐      ┌───────────┐                    │
│    │  Task     │      │ Execution │      │  Result   │                    │
│    │  Input    │ ───► │  Engine   │ ───► │  Output   │                    │
│    └───────────┘      └───────────┘      └───────────┘                    │
│         │                  │                  │                           │
│         │                  │                  │                           │
│         ▼                  ▼                  ▼                           │
│    ┌─────────────────────────────────────────────────────────────────┐    │
│    │                    Experience Collector                          │    │
│    │  - 任务上下文                                                      │    │
│    │  - 工具调用记录                                                    │    │
│    │  - 错误/成功日志                                                   │    │
│    │  - 用户反馈                                                        │    │
│    └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                       │
│                                    ▼                                       │
│    ┌─────────────────────────────────────────────────────────────────┐    │
│    │                    Experience Store                               │    │
│    │  - ExecutionTrace (执行轨迹)                                      │    │
│    │  - Feedback (反馈记录)                                            │    │
│    │  - Pattern (成功模式)                                             │    │
│    └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                       │
│                                    ▼                                       │
│    ┌─────────────────────────────────────────────────────────────────┐    │
│    │                    Evolution Engine                               │    │
│    │                                                                   │    │
│    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │    │
│    │  │  Analyzer   │  │  Generator  │  │  Validator             │  │    │
│    │  │  (分析器)    │  │  (生成器)    │  │  (验证器)              │  │    │
│    │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │    │
│    │                                                                   │    │
│    │  分析执行模式 → 生成新能力/优化 → 验证效果                         │    │
│    └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                       │
│                                    ▼                                       │
│    ┌─────────────────────────────────────────────────────────────────┐    │
│    │                    Capability Registry                           │    │
│    │  - 新技能注册                                                     │    │
│    │  - 技能优化                                                       │    │
│    │  - 能力评估                                                       │    │
│    └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                       │
│                                    ▼                                       │
│                              [返回下一任务]                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 核心组件设计

#### 5.2.1 ExperienceStore (经验存储)

```python
# src/openakita/evolution/experience_store.py

@dataclass
class ExecutionTrace:
    """执行轨迹"""
    trace_id: str
    task_id: str
    task_description: str

    # 执行步骤
    steps: list[dict] = field(default_factory=list)

    # 工具调用
    tool_calls: list[dict] = field(default_factory=list)

    # 结果
    success: bool = False
    error_message: str = ""

    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0
    token_usage: int = 0

    # 用户反馈 (可选)
    user_rating: int | None = None      # 1-5
    user_comment: str | None = None


@dataclass
class SuccessPattern:
    """成功模式"""
    pattern_id: str
    pattern_type: str                    # "workflow", "tool_sequence", "prompt_template"

    # 模式内容
    description: str
    template: dict                       # 可复用的模板

    # 统计
    success_count: int = 0
    total_count: int = 0
    success_rate: float = 0.0

    # 标签
    tags: list[str] = field(default_factory=list)


class ExperienceStore:
    """
    经验存储

    职责：
    - 存储执行轨迹
    - 提取成功模式
    - 支持检索与学习
    """

    def __init__(self, store_path: Path):
        self._path = store_path
        self._traces: dict[str, ExecutionTrace] = {}
        self._patterns: dict[str, SuccessPattern] = {}

    def record_trace(self, trace: ExecutionTrace) -> None:
        """记录执行轨迹"""
        self._traces[trace.trace_id] = trace
        self._persist_trace(trace)

    def record_feedback(
        self,
        trace_id: str,
        rating: int,
        comment: str | None = None,
    ) -> None:
        """记录用户反馈"""
        trace = self._traces.get(trace_id)
        if trace:
            trace.user_rating = rating
            trace.user_comment = comment
            self._persist_trace(trace)

    def extract_patterns(self) -> list[SuccessPattern]:
        """从轨迹中提取成功模式"""
        patterns = []

        # 1. 提取工具序列模式
        patterns.extend(self._extract_tool_sequences())

        # 2. 提取工作流模式
        patterns.extend(self._extract_workflow_patterns())

        # 3. 提取提示模板模式
        patterns.extend(self._extract_prompt_patterns())

        return patterns

    def _extract_tool_sequences(self) -> list[SuccessPattern]:
        """提取成功的工具调用序列"""
        # 分析成功的轨迹，找出高频工具组合
        pass

    def _extract_workflow_patterns(self) -> list[SuccessPattern]:
        """提取工作流模式"""
        # 分析任务解决步骤，识别可复用流程
        pass

    def _extract_prompt_patterns(self) -> list[SuccessPattern]:
        """提取提示模板模式"""
        # 分析有效的提示模式
        pass

    def search_similar_traces(
        self,
        task_description: str,
        top_k: int = 5,
    ) -> list[ExecutionTrace]:
        """搜索相似的历史轨迹"""
        # 使用向量相似度搜索
        pass

    def get_successful_traces(self, limit: int = 100) -> list[ExecutionTrace]:
        """获取成功的轨迹"""
        return [
            t for t in self._traces.values()
            if t.success and t.user_rating and t.user_rating >= 4
        ][:limit]
```

#### 5.2.2 SkillEvolver (技能进化器)

```python
# src/openakita/evolution/skill_evolver.py

@dataclass
class EvolutionProposal:
    """进化提案"""
    proposal_id: str
    proposal_type: str              # "new_skill", "optimize", "deprecate"
    skill_name: str
    description: str
    rationale: str                  # 进化理由
    suggested_content: str         # 建议的 SKILL.md 内容
    confidence: float              # 置信度 0-1
    source_traces: list[str]        # 来源轨迹 ID


class SkillEvolver:
    """
    技能进化器

    职责：
    - 分析经验数据
    - 提出技能改进建议
    - 生成新技能
    """

    def __init__(
        self,
        experience_store: ExperienceStore,
        brain: "Brain",
        skill_registry: "SkillRegistry",
    ):
        self._store = experience_store
        self._brain = brain
        self._registry = skill_registry

    async def analyze_and_propose(self) -> list[EvolutionProposal]:
        """分析并生成进化提案"""
        proposals = []

        # 1. 检测缺失能力
        proposals.extend(await self._detect_missing_capabilities())

        # 2. 检测优化机会
        proposals.extend(await self._detect_optimization_opportunities())

        # 3. 检测废弃技能
        proposals.extend(await self._detect_deprecated_skills())

        return proposals

    async def _detect_missing_capabilities(self) -> list[EvolutionProposal]:
        """检测缺失的能力"""
        proposals = []

        # 分析失败轨迹
        failed_traces = [
            t for t in self._store._traces.values()
            if not t.success
        ]

        # 分析失败原因
        # 如果某种任务类型频繁失败且原因与工具缺失相关
        # 提出创建新技能的提案
        pass

        return proposals

    async def _detect_optimization_opportunities(self) -> list[EvolutionProposal]:
        """检测优化机会"""
        proposals = []

        # 分析成功模式
        patterns = self._store.extract_patterns()

        for pattern in patterns:
            if pattern.success_rate > 0.8:
                # 高成功率模式 -> 可固化成技能
                proposal = await self._create_skill_proposal(pattern)
                proposals.append(proposal)

        return proposals

    async def _detect_deprecated_skills(self) -> list[EvolutionProposal]:
        """检测废弃技能"""
        proposals = []

        # 检查技能使用统计
        for skill in self._registry.list_all():
            stats = self._registry.get_stats(skill.name)
            if stats.call_count > 10 and stats.success_rate < 0.3:
                # 使用率高但成功率低 -> 建议优化或废弃
                pass

        return proposals

    async def generate_skill(self, proposal: EvolutionProposal) -> str:
        """根据提案生成技能"""
        # 使用 LLM 生成 SKILL.md
        prompt = f"""
        根据以下经验数据，生成一个新的 SKILL.md 技能定义：

        提案：{proposal.description}
        理由：{proposal.rationale}

        请按照 SKILL.md 规范生成技能内容。
        """

        response = await self._brain.think(prompt)
        return response.content

    async def apply_proposal(self, proposal: EvolutionProposal) -> bool:
        """应用进化提案"""
        if proposal.proposal_type == "new_skill":
            skill_content = await self.generate_skill(proposal)
            # 保存技能文件
            skill_path = self._registry.skills_dir / proposal.skill_name / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(skill_content)
            return True

        elif proposal.proposal_type == "optimize":
            # 更新现有技能
            pass

        elif proposal.proposal_type == "deprecate":
            # 标记废弃
            pass

        return False
```

#### 5.2.3 KnowledgeDistiller (知识蒸馏器)

```python
# src/openakita/evolution/knowledge_distiller.py

@dataclass
class KnowledgeEntry:
    """知识条目"""
    entry_id: str
    category: str                    # "fact", "procedure", "pattern", "insight"
    title: str
    content: str
    source: str                      # 来源轨迹/任务
    confidence: float
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0


class KnowledgeDistiller:
    """
    知识蒸馏器

    职责：
    - 从执行轨迹中提取知识
    - 蒸馏生成 MEMORY.md 内容
    - 管理知识的生命周期
    """

    def __init__(
        self,
        experience_store: ExperienceStore,
        brain: "Brain",
        memory_path: Path,
    ):
        self._store = experience_store
        self._brain = brain
        self._memory_path = memory_path
        self._knowledge: dict[str, KnowledgeEntry] = {}

    async def distill(self) -> None:
        """执行知识蒸馏"""
        # 1. 收集新的执行轨迹
        new_traces = self._get_unprocessed_traces()

        if not new_traces:
            return

        # 2. 提取知识候选
        candidates = await self._extract_knowledge_candidates(new_traces)

        # 3. 验证知识
        validated = await self._validate_knowledge(candidates)

        # 4. 合并到知识库
        for entry in validated:
            self._knowledge[entry.entry_id] = entry

        # 5. 更新 MEMORY.md
        await self._update_memory_file()

        # 6. 标记轨迹已处理
        self._mark_traces_processed(new_traces)

    async def _extract_knowledge_candidates(
        self,
        traces: list[ExecutionTrace],
    ) -> list[KnowledgeEntry]:
        """从轨迹提取知识候选"""
        candidates = []

        for trace in traces:
            if not trace.success or not trace.user_rating or trace.user_rating < 4:
                continue

            # 使用 LLM 提取可复用的知识
            prompt = f"""
            从以下成功的任务执行中提取可复用的知识：

            任务：{trace.task_description}
            步骤：{json.dumps(trace.steps, ensure_ascii=False)}
            工具调用：{json.dumps(trace.tool_calls, ensure_ascii=False)}

            请提取：
            1. 事实性知识 (facts)
            2. 过程性知识 (procedures)
            3. 模式性知识 (patterns)
            4. 洞察性知识 (insights)

            以 JSON 格式返回提取的知识列表。
            """

            response = await self._brain.think(prompt)
            # 解析并创建 KnowledgeEntry
            pass

        return candidates

    async def _validate_knowledge(
        self,
        candidates: list[KnowledgeEntry],
    ) -> list[KnowledgeEntry]:
        """验证知识的有效性"""
        validated = []

        for entry in candidates:
            # 检查是否与现有知识冲突
            conflicts = self._find_conflicts(entry)

            if conflicts:
                # 解决冲突
                resolved = await self._resolve_conflicts(entry, conflicts)
                if resolved:
                    validated.append(entry)
            else:
                validated.append(entry)

        return validated

    async def _update_memory_file(self) -> None:
        """更新 MEMORY.md"""
        # 按类别组织知识
        sections = {
            "fact": "## 事实知识\n",
            "procedure": "## 过程知识\n",
            "pattern": "## 模式知识\n",
            "insight": "## 洞察知识\n",
        }

        for entry in self._knowledge.values():
            section = sections.get(entry.category, "")
            section += f"\n### {entry.title}\n{entry.content}\n"
            sections[entry.category] = section

        content = "# 长期记忆\n\n" + "\n".join(sections.values())
        self._memory_path.write_text(content)

    def query(self, query: str, top_k: int = 5) -> list[KnowledgeEntry]:
        """查询知识"""
        # 使用向量搜索
        pass
```

### 5.3 EvolutionOrchestrator (进化编排器)

```python
# src/openakita/evolution/orchestrator.py

class EvolutionOrchestrator:
    """
    进化编排器 - 统一协调进化流程

    职责：
    - 定期触发进化分析
    - 协调各组件工作
    - 管理进化配置
    """

    def __init__(
        self,
        experience_store: ExperienceStore,
        skill_evolver: SkillEvolver,
        knowledge_distiller: KnowledgeDistiller,
        capability_registry: CapabilityRegistry,
    ):
        self._store = experience_store
        self._evolver = skill_evolver
        self._distiller = knowledge_distiller
        self._registry = capability_registry

        self._config = EvolutionConfig()
        self._last_evolution: datetime | None = None

    async def run_evolution_cycle(self) -> EvolutionReport:
        """运行进化周期"""
        report = EvolutionReport(
            started_at=datetime.now(),
        )

        try:
            # 1. 知识蒸馏
            await self._distiller.distill()
            report.knowledge_distilled = True

            # 2. 分析并提案
            proposals = await self._evolver.analyze_and_propose()
            report.proposals_generated = len(proposals)

            # 3. 自动应用高置信度提案
            for proposal in proposals:
                if proposal.confidence >= self._config.auto_apply_threshold:
                    success = await self._evolver.apply_proposal(proposal)
                    if success:
                        report.proposals_applied += 1
                        report.applied_skills.append(proposal.skill_name)

            # 4. 清理过期知识
            cleaned = await self._cleanup_stale_knowledge()
            report.knowledge_cleaned = cleaned

            report.success = True

        except Exception as e:
            report.success = False
            report.error = str(e)

        finally:
            report.completed_at = datetime.now()
            self._last_evolution = report.completed_at

        return report

    async def _cleanup_stale_knowledge(self) -> int:
        """清理过期知识"""
        cleaned = 0
        threshold = datetime.now() - timedelta(days=self._config.knowledge_ttl_days)

        for entry_id, entry in list(self._distiller._knowledge.items()):
            if entry.updated_at < threshold and entry.usage_count == 0:
                del self._distiller._knowledge[entry_id]
                cleaned += 1

        return cleaned

    def should_evolve(self) -> bool:
        """判断是否应该触发进化"""
        if not self._last_evolution:
            return True

        elapsed = datetime.now() - self._last_evolution
        return elapsed >= timedelta(hours=self._config.evolution_interval_hours)


@dataclass
class EvolutionConfig:
    """进化配置"""
    evolution_interval_hours: int = 24      # 进化周期
    auto_apply_threshold: float = 0.8       # 自动应用阈值
    knowledge_ttl_days: int = 30            # 知识保留天数
    min_traces_for_evolution: int = 10      # 最少轨迹数


@dataclass
class EvolutionReport:
    """进化报告"""
    started_at: datetime
    completed_at: datetime | None = None
    success: bool = False
    error: str | None = None

    knowledge_distilled: bool = False
    proposals_generated: int = 0
    proposals_applied: int = 0
    applied_skills: list[str] = field(default_factory=list)
    knowledge_cleaned: int = 0
```

### 5.4 进化层目录结构

```
evolution/
├── __init__.py
├── orchestrator.py        # EvolutionOrchestrator (主入口)
├── config.py              # EvolutionConfig
├── experience_store.py    # ExperienceStore (经验存储)
├── skill_evolver.py       # SkillEvolver (技能进化)
├── knowledge_distiller.py # KnowledgeDistiller (知识蒸馏)
├── pattern_analyzer.py    # PatternAnalyzer (模式分析)
├── validator.py           # EvolutionValidator (效果验证)
├── types.py               # 数据类型定义
└── exceptions.py          # 异常定义
```

---

## 六、集成方案

### 6.1 Agent 集成

```python
# src/openakita/core/agent.py (修改)

class Agent:
    """企业级 Agent"""

    def __init__(self, config: AgentConfig | None = None):
        # ... 现有初始化 ...

        # 新增：上下文编排器
        self.context_orchestrator = ContextOrchestrator(
            system_ctx=self._init_system_context(),
        )

        # 新增：统一能力注册表
        self.capability_registry = CapabilityRegistry()

        # 新增：进化编排器
        self.evolution_orchestrator = EvolutionOrchestrator(
            experience_store=ExperienceStore(data_path / "experiences"),
            skill_evolver=SkillEvolver(...),
            knowledge_distiller=KnowledgeDistiller(...),
            capability_registry=self.capability_registry,
        )

    async def initialize(self) -> None:
        """初始化 Agent"""
        # 1. 加载能力到统一注册表
        await self._load_capabilities()

        # 2. 初始化上下文
        await self._init_contexts()

        # 3. 启动进化调度
        self._start_evolution_scheduler()

    async def _load_capabilities(self) -> None:
        """加载所有能力"""
        # 加载本地工具
        for tool in self.tool_catalog.list_all():
            self.capability_registry.register(
                self._convert_tool_to_capability(tool),
                self.tool_executor.execute,
            )

        # 加载技能
        for skill in self.skill_manager.registry.list_all():
            self.capability_registry.register(
                self._convert_skill_to_capability(skill),
                self.skill_manager.execute,
            )

        # 加载 MCP 工具
        for mcp_tool in self.mcp_manager.list_tools():
            self.capability_registry.register(
                self._convert_mcp_to_capability(mcp_tool),
                self.mcp_manager.call_tool,
            )

    async def run_task(self, task: str) -> str:
        """运行任务"""
        # 1. 创建任务上下文
        task_id = generate_uuid()
        self.context_orchestrator.create_task(
            task_id=task_id,
            tenant_id=self.tenant_id,
            description=task,
        )

        # 2. 记录执行轨迹
        trace = ExecutionTrace(
            trace_id=generate_uuid(),
            task_id=task_id,
            task_description=task,
        )

        try:
            # 3. 执行任务 (使用上下文编排器)
            result = await self._execute_task(task_id, task)

            # 4. 记录成功
            trace.success = True
            trace.duration_ms = elapsed_ms()

            return result

        except Exception as e:
            trace.success = False
            trace.error_message = str(e)
            raise

        finally:
            # 5. 存储轨迹
            self.evolution_orchestrator._store.record_trace(trace)
```

### 6.2 配置集成

```yaml
# config/evolution.yaml

evolution:
  # 进化周期配置
  interval_hours: 24

  # 自动应用阈值
  auto_apply_threshold: 0.8

  # 知识管理
  knowledge:
    ttl_days: 30
    min_confidence: 0.7

  # 技能进化
  skill:
    min_traces_for_new: 10
    success_rate_threshold: 0.8

  # 存储配置
  storage:
    experience_path: "data/experiences"
    knowledge_path: "data/knowledge"
    pattern_path: "data/patterns"
```

---

## 七、实施路线图

### Phase 1: 上下文层重构 (1-2 周)

| 任务 | 说明 |
|------|------|
| 1.1 | 完善 SystemContext, TaskContext, ConversationContext |
| 1.2 | 实现 ContextOrchestrator |
| 1.3 | 集成 Token 预算管理 |
| 1.4 | 迁移 Agent 到新上下文系统 |

### Phase 2: 能力层统一 (1 周)

| 任务 | 说明 |
|------|------|
| 2.1 | 实现 CapabilityRegistry |
| 2.2 | 实现各类型适配器 |
| 2.3 | 统一工具/技能/MCP 接口 |
| 2.4 | 更新 ToolExecutor |

### Phase 3: 进化层实现 (2 周)

| 任务 | 说明 |
|------|------|
| 3.1 | 实现 ExperienceStore |
| 3.2 | 实现 SkillEvolver |
| 3.3 | 实现 KnowledgeDistiller |
| 3.4 | 实现 EvolutionOrchestrator |
| 3.5 | 集成到 Agent |

### Phase 4: 测试与优化 (1 周)

| 任务 | 说明 |
|------|------|
| 4.1 | 单元测试 |
| 4.2 | 集成测试 |
| 4.3 | 性能优化 |
| 4.4 | 文档完善 |

---

## 八、总结

本方案提出的企业级可自我进化 Agent 架构，核心改进包括：

1. **分层上下文管理**：System/Task/Conversation 三层架构，Token 预算动态分配
2. **统一能力注册表**：Tool/Skill/MCP 统一接口，插件化架构
3. **闭环进化机制**：执行轨迹 → 经验沉淀 → 模式提取 → 技能进化 → 效果验证

该架构遵循高内聚低耦合原则，各模块职责清晰，通过接口通信，支持独立测试和迭代。