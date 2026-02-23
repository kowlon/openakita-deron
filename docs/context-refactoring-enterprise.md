# 上下文管理分析与重构方案

> 最后更新: 2026-02-23

## 一、现有上下文管理分析

### 1.1 架构概览

```
┌────────────────────────────────────────────────────────────────┐
│                        Agent (Brain)                           │
├────────────────────────────────────────────────────────────────┤
│  System Prompt (静态)                                          │
│  ├── Identity 层 (soul/agent_core/agent_tooling/policies)      │
│  ├── Persona 层 (人格描述)                                      │
│  ├── Runtime 层 (运行时信息)                                    │
│  ├── Catalogs 层 (tools/skills 清单)                           │
│  ├── Memory 层 (检索的记忆)                                     │
│  └── User 层 (用户信息)                                        │
├────────────────────────────────────────────────────────────────┤
│  Messages (动态)                                               │
│  ├── 历史对话 (可能被压缩)                                      │
│  ├── 工具调用/结果 (tool_use/tool_result)                       │
│  └── 当前用户消息                                               │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 核心文件与职责

| 文件 | 职责 | 代码量 |
|-----|------|-------|
| `core/context_manager.py` | 上下文压缩、token 估算 | ~400 行 |
| `core/agent.py` | 上下文准备、注入 | ~2000 行 |
| `sessions/session.py` | 会话状态管理 | ~300 行 |
| `sessions/manager.py` | 会话生命周期 | ~200 行 |
| `prompt/builder.py` | 系统提示词组装 | ~500 行 |

### 1.3 上下文生命周期

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  创建    │ ──▶ │  更新    │ ──▶ │  压缩    │ ──▶ │  销毁    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                │                │
     ▼                ▼                ▼                ▼
 Agent.init()     每轮对话        token 超限        会话过期
                  add_message()   soft_limit 70%   30分钟超时
```

### 1.4 压缩机制详解

**触发条件：**
```python
# 当前 tokens > soft_limit (70% 硬限制)
# 或消息数 > 100 条
if current_tokens > soft_limit or message_count > 100:
    compress()
```

**压缩流程：**
```
1. 单条大内容压缩 (>5000 tokens 的 tool_result)
2. 工具调用分组 (保证 tool_use/tool_result 配对)
3. 保留最近 4 轮对话
4. LLM 分块摘要早期对话 (压缩到 15%)
5. 递归压缩 (仍超限则减少保留轮次)
6. 硬截断保底
```

### 1.5 现有问题分析

| 问题 | 描述 | 严重程度 |
|-----|------|---------|
| **LLM 压缩开销大** | 每次压缩调用 LLM，延迟 2-5 秒 | 🔴 高 |
| **压缩时机被动** | 只在超限时触发，可能导致突然卡顿 | 🟡 中 |
| **无优先级区分** | 所有消息同等对待，可能丢失关键信息 | 🟡 中 |
| **会话无限增长** | 清理依赖超时，高频场景内存压力大 | 🟡 中 |
| **企业场景不适配** | 无多租户隔离、无任务级上下文 | 🔴 高 |

---

## 二、企业级上下文改进方案

### 2.1 设计原则

```
1. 简洁可靠 - 移除 LLM 依赖，使用确定性算法
2. 任务导向 - 上下文围绕任务，任务结束即清理
3. 分层管理 - 系统级/任务级/会话级分离
4. 可控可观测 - 大小可控，状态可监控
```

### 2.2 三层上下文架构

```
┌────────────────────────────────────────────────────────────────┐
│                    Enterprise Context                           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Layer 1: System Context (系统上下文)                     │   │
│  │ - 生命周期: 永久                                         │   │
│  │ - 内容: 身份、规则、工具清单                              │   │
│  │ - 大小: 固定上限 (如 8K tokens)                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Layer 2: Task Context (任务上下文)                       │   │
│  │ - 生命周期: 任务期间                                     │   │
│  │ - 内容: 任务定义、步骤状态、关键变量                      │   │
│  │ - 大小: 动态但有上限 (如 16K tokens)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Layer 3: Conversation Context (对话上下文)               │   │
│  │ - 生命周期: 当前轮次                                     │   │
│  │ - 内容: 最近 N 轮对话、工具调用结果                       │   │
│  │ - 大小: 滑动窗口 (如 8K tokens, 最近 20 轮)              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 2.3 各层详细设计

#### Layer 1: System Context

**特点：**
- 预编译，启动时加载
- 只读，运行时不修改
- 固定大小，超出需精简配置

**数据结构：**
```python
@dataclass
class SystemContext:
    """系统上下文 - 永久只读"""

    # 身份信息 (来自 identity/)
    identity: str              # Agent 身份描述

    # 业务规则 (来自配置)
    rules: list[str]           # 业务约束规则

    # 工具清单
    tools_manifest: str        # 可用工具描述

    # 预估 token 数
    token_count: int

    # 约束
    MAX_TOKENS = 8000

    def to_prompt(self) -> str:
        """生成系统提示词"""
        return f"""# 身份
{self.identity}

# 规则
{chr(10).join(f'- {r}' for r in self.rules)}

# 可用工具
{self.tools_manifest}
"""
```

#### Layer 2: Task Context

**特点：**
- 任务开始时创建
- 任务结束时销毁
- 动态更新，有上限

**数据结构：**
```python
@dataclass
class TaskContext:
    """任务上下文 - 任务期间有效"""

    task_id: str
    tenant_id: str

    # 任务定义
    task_type: str             # 任务类型标识
    task_description: str      # 任务描述

    # 执行状态
    current_step: int          # 当前步骤
    total_steps: int           # 总步骤数
    step_summaries: list[str]  # 已完成步骤摘要 (每条 <100 字)

    # 关键变量 (任务执行中提取的)
    key_variables: dict[str, str]  # 变量名 -> 值描述

    # 错误记录
    errors: list[ErrorEntry]

    # 约束
    MAX_SUMMARIES = 20         # 最多保留 20 个步骤摘要
    MAX_VARIABLES = 50         # 最多 50 个变量
    MAX_TOKENS = 16000

    def add_step_summary(self, step_name: str, summary: str):
        """添加步骤摘要，自动截断"""
        entry = f"[{step_name}] {summary[:100]}"
        self.step_summaries.append(entry)
        # 滑动窗口：保留最近 20 条
        if len(self.step_summaries) > self.MAX_SUMMARIES:
            self.step_summaries = self.step_summaries[-self.MAX_SUMMARIES:]

    def to_prompt(self) -> str:
        """生成任务上下文提示"""
        parts = [f"# 当前任务\n{self.task_description}"]

        if self.step_summaries:
            parts.append("# 已完成步骤\n" + "\n".join(self.step_summaries))

        if self.key_variables:
            parts.append("# 关键变量\n" + "\n".join(
                f"- {k}: {v}" for k, v in self.key_variables.items()
            ))

        return "\n\n".join(parts)


@dataclass
class ErrorEntry:
    step: str
    error_type: str
    message: str
    resolved: bool
    resolution: str | None = None
```

#### Layer 3: Conversation Context

**特点：**
- 滑动窗口，自动淘汰旧消息
- 无 LLM 压缩，确定性截断
- 保留最近的完整对话轮次

**数据结构：**
```python
@dataclass
class ConversationContext:
    """对话上下文 - 滑动窗口"""

    messages: list[dict]        # 对话消息

    # 约束
    MAX_TOKENS = 8000
    MAX_ROUNDS = 20             # 最多 20 轮对话
    MIN_KEEP_ROUNDS = 4         # 至少保留 4 轮

    def add_message(self, role: str, content: str | list):
        """添加消息，自动维护窗口"""
        self.messages.append({"role": role, "content": content})
        self._trim_if_needed()

    def _trim_if_needed(self):
        """滑动窗口裁剪 - 确定性算法，无 LLM 调用"""
        # 1. 按轮次限制
        rounds = self._count_rounds()
        if rounds <= self.MAX_ROUNDS:
            return

        # 2. 保留最近 N 轮
        keep_from = self._find_round_boundary(rounds - self.MAX_ROUNDS)
        self.messages = self.messages[keep_from:]

    def _count_rounds(self) -> int:
        """计算对话轮次 (user 消息数)"""
        return sum(1 for m in self.messages if m["role"] == "user")

    def _find_round_boundary(self, target_round: int) -> int:
        """找到第 N 轮的起始索引"""
        round_count = 0
        for i, msg in enumerate(self.messages):
            if msg["role"] == "user":
                round_count += 1
                if round_count > target_round:
                    return i
        return 0

    def to_messages(self) -> list[dict]:
        """返回消息列表"""
        return self.messages.copy()
```

### 2.4 上下文管理器 (统一入口)

```python
class EnterpriseContextManager:
    """
    企业级上下文管理器
    统一管理三层上下文，提供简洁接口
    """

    def __init__(self, config: ContextConfig):
        self.config = config
        self.system_ctx: SystemContext | None = None
        self.task_contexts: dict[str, TaskContext] = {}  # task_id -> context
        self.conversation_contexts: dict[str, ConversationContext] = {}  # session_id -> context

    # ========== 初始化 ==========

    def initialize(self, identity: str, rules: list[str], tools_manifest: str):
        """初始化系统上下文（启动时调用一次）"""
        self.system_ctx = SystemContext(
            identity=identity,
            rules=rules,
            tools_manifest=tools_manifest,
            token_count=self._estimate_tokens(identity + "".join(rules) + tools_manifest)
        )

    # ========== 任务管理 ==========

    def start_task(self, task_id: str, tenant_id: str, task_type: str, description: str):
        """开始任务，创建任务上下文"""
        self.task_contexts[task_id] = TaskContext(
            task_id=task_id,
            tenant_id=tenant_id,
            task_type=task_type,
            task_description=description,
            current_step=0,
            total_steps=0,
            step_summaries=[],
            key_variables={},
            errors=[]
        )

    def end_task(self, task_id: str):
        """结束任务，销毁任务上下文"""
        self.task_contexts.pop(task_id, None)
        # 同时清理关联的对话上下文
        to_remove = [sid for sid, ctx in self.conversation_contexts.items()
                     if sid.startswith(task_id)]
        for sid in to_remove:
            self.conversation_contexts.pop(sid, None)

    def update_task_step(self, task_id: str, step_name: str, summary: str):
        """更新任务步骤"""
        ctx = self.task_contexts.get(task_id)
        if ctx:
            ctx.add_step_summary(step_name, summary)

    def set_task_variable(self, task_id: str, name: str, value: str):
        """设置任务变量"""
        ctx = self.task_contexts.get(task_id)
        if ctx:
            ctx.key_variables[name] = value[:200]  # 限制变量值长度

    # ========== 对话管理 ==========

    def get_or_create_conversation(self, session_id: str) -> ConversationContext:
        """获取或创建对话上下文"""
        if session_id not in self.conversation_contexts:
            self.conversation_contexts[session_id] = ConversationContext(messages=[])
        return self.conversation_contexts[session_id]

    def add_message(self, session_id: str, role: str, content: str | list):
        """添加消息"""
        ctx = self.get_or_create_conversation(session_id)
        ctx.add_message(role, content)

    # ========== 上下文组装 ==========

    def build_full_context(self, task_id: str, session_id: str) -> tuple[str, list[dict]]:
        """
        构建完整上下文
        返回: (system_prompt, messages)
        """
        parts = []

        # Layer 1: 系统上下文
        if self.system_ctx:
            parts.append(self.system_ctx.to_prompt())

        # Layer 2: 任务上下文
        task_ctx = self.task_contexts.get(task_id)
        if task_ctx:
            parts.append(task_ctx.to_prompt())

        system_prompt = "\n\n---\n\n".join(parts)

        # Layer 3: 对话上下文
        conv_ctx = self.conversation_contexts.get(session_id)
        messages = conv_ctx.to_messages() if conv_ctx else []

        return system_prompt, messages

    # ========== Token 估算 ==========

    def _estimate_tokens(self, text: str) -> int:
        """简化的 token 估算"""
        # 中文约 1.5 字符/token，英文约 4 字符/token
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english = len(text) - chinese
        return int(chinese / 1.5 + english / 4)

    def get_context_stats(self, task_id: str, session_id: str) -> dict:
        """获取上下文统计信息"""
        task_ctx = self.task_contexts.get(task_id)
        conv_ctx = self.conversation_contexts.get(session_id)

        return {
            "system_tokens": self.system_ctx.token_count if self.system_ctx else 0,
            "task_tokens": self._estimate_tokens(task_ctx.to_prompt()) if task_ctx else 0,
            "conversation_tokens": sum(
                self._estimate_tokens(str(m)) for m in conv_ctx.messages
            ) if conv_ctx else 0,
            "task_steps": len(task_ctx.step_summaries) if task_ctx else 0,
            "conversation_rounds": conv_ctx._count_rounds() if conv_ctx else 0,
        }
```

### 2.5 与现有方案的对比

| 维度 | 现有方案 | 企业方案 |
|-----|---------|---------|
| **压缩方式** | LLM 分块摘要 | **滑动窗口 + 步骤摘要** |
| **压缩延迟** | 2-5 秒 | **<10ms** |
| **LLM 依赖** | 强依赖 | **无依赖** |
| **上下文层次** | 单层 messages | **三层分离** |
| **任务隔离** | 无 | **按 task_id 隔离** |
| **生命周期** | 超时清理 | **任务结束即清理** |
| **可观测性** | 弱 | **stats 接口** |
| **可控性** | 自动 | **可配置窗口大小** |

### 2.6 性能对比

| 操作 | 现有方案 | 企业方案 |
|-----|---------|---------|
| 添加消息 | O(1) | O(1) |
| 触发压缩 | 2-5s (LLM) | **<10ms** (数组切片) |
| 上下文构建 | ~100ms | **<10ms** |
| 内存占用 | 不确定 | **可控上限** |

---

## 三、迁移方案

### 3.1 兼容层设计

```python
class ContextBackend(Protocol):
    """上下文后端协议"""

    def build_context(self, task_id: str, session_id: str) -> tuple[str, list[dict]]: ...
    def add_message(self, session_id: str, role: str, content: str | list): ...
    def compress_if_needed(self, session_id: str) -> bool: ...


class LegacyContextBackend(ContextBackend):
    """兼容现有系统"""

    def __init__(self, context_manager: ContextManager):
        self.cm = context_manager

    def build_context(self, task_id: str, session_id: str) -> tuple[str, list[dict]]:
        # 调用现有的压缩逻辑
        messages = self.cm.compress_if_needed(...)
        return system_prompt, messages


class EnterpriseContextBackend(ContextBackend):
    """企业级实现"""

    def __init__(self, manager: EnterpriseContextManager):
        self.manager = manager

    def build_context(self, task_id: str, session_id: str) -> tuple[str, list[dict]]:
        return self.manager.build_full_context(task_id, session_id)

    def compress_if_needed(self, session_id: str) -> bool:
        # 企业版不需要显式压缩，滑动窗口自动处理
        return True
```

### 3.2 配置切换

```yaml
# config.yaml
context:
  backend: enterprise  # legacy | enterprise

  enterprise:
    max_conversation_rounds: 20
    max_task_summaries: 20
    max_task_variables: 50
    system_context_max_tokens: 8000
    task_context_max_tokens: 16000
    conversation_context_max_tokens: 8000
```

### 3.3 迁移步骤

```
Phase 1: 抽象接口
├── 定义 ContextBackend 协议
└── 将现有代码封装为 LegacyContextBackend

Phase 2: 实现企业版
├── 实现 EnterpriseContextManager
├── 实现三层上下文数据结构
└── 实现滑动窗口裁剪

Phase 3: 灰度切换
├── 通过配置选择 backend
└── 新任务使用企业版

Phase 4: 完全迁移
├── 移除 Legacy 依赖
└── 简化 Agent 代码
```

---

## 四、代码结构建议

```
src/openakita/context/
├── __init__.py
├── protocol.py              # ContextBackend 协议
│
├── enterprise/              # 企业级实现
│   ├── __init__.py
│   ├── manager.py           # EnterpriseContextManager
│   ├── system_context.py    # SystemContext
│   ├── task_context.py      # TaskContext
│   ├── conversation_context.py  # ConversationContext
│   └── config.py            # 配置类
│
├── legacy/                  # 现有实现
│   ├── __init__.py
│   ├── context_manager.py   # 现有代码
│   └── adapter.py           # LegacyContextBackend
│
└── utils/
    ├── token_estimator.py   # Token 估算
    └── stats.py             # 统计工具
```

---

## 五、总结

### 核心改进点

1. **移除 LLM 压缩** → 滑动窗口 + 步骤摘要，延迟从秒级降到毫秒级
2. **三层分离** → 系统/任务/对话独立管理，职责清晰
3. **任务导向** → 任务结束即清理，避免上下文污染
4. **确定性** → 无 LLM 调用，行为可预测
5. **可观测** → stats 接口实时监控上下文状态

### 适用场景

- ✅ 任务导向的企业应用
- ✅ 多租户隔离需求
- ✅ 低延迟要求
- ✅ 需要可控的上下文大小
- ❌ 需要保留完整对话历史的场景（建议使用 Legacy）

---

## 六、待确认事项

请确认以下几点：

1. **滑动窗口大小**：20 轮对话是否合适？需要可配置吗？
2. **步骤摘要格式**：当前设计为 `[步骤名] 摘要内容`，是否需要更结构化？
3. **变量存储**：任务变量是否需要持久化（任务恢复场景）？
4. **错误记录**：错误信息是否需要注入到上下文？还是仅日志记录？
5. **多模态内容**：图片/文件等大内容如何处理？是否需要单独的存储？
