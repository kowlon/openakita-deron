# Memory 系统分析与企业应用重构方案

> 最后更新: 2026-02-23

## 一、现有 Memory 系统分析

### 1.1 系统架构概览

当前的 memory 系统是为 C 端用户设计的"全存储"模式，采用三层架构：

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent 主循环                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 短期记忆    │    │ 工作记忆    │    │ 长期记忆    │
│ (Session)   │    │ (MEMORY.md) │    │ (ChromaDB)  │
└─────────────┘    └─────────────┘    └─────────────┘
   对话历史           精华摘要            向量索引
```

### 1.2 核心组件清单

| 文件路径 | 职责 | 代码行数估计 |
|---------|------|-------------|
| `src/openakita/memory/manager.py` | 记忆管理器核心 | ~500 |
| `src/openakita/memory/vector_store.py` | 向量存储与搜索 | ~300 |
| `src/openakita/memory/extractor.py` | AI 提取记忆 | ~400 |
| `src/openakita/memory/daily_consolidator.py` | 每日归纳 | ~300 |
| `src/openakita/memory/types.py` | 类型定义 | ~100 |
| `src/openakita/core/context_manager.py` | 上下文压缩 | ~400 |
| `src/openakita/tools/handlers/memory.py` | 工具处理器 | ~200 |

**总计：约 2200 行核心代码**

### 1.3 数据流详解

#### 1.3.1 写入流程

```python
# 用户消息触发
user_input → record_turn() → extract_from_turn_with_ai() → add_memory()

# 具体流程:
1. Agent 收到用户消息
2. 调用 memory_manager.record_turn(role="user", content=...)
3. AI 判断是否值得记录（调用 LLM）
4. 若值得记录：
   a. 生成 Memory 对象（type, priority, content, tags）
   b. 写入 memories.json
   c. 计算 embedding 存入 ChromaDB
   d. 更新 access_count
```

#### 1.3.2 读取流程

```python
# 记忆注入流程
task_query → get_injection_context() → 返回记忆上下文

# 具体流程:
1. 读取 MEMORY.md 精华（~800 字符）
2. 对 task_query 计算 embedding
3. ChromaDB 语义搜索 top-k 相关记忆
4. 若 ChromaDB 不可用，回退关键词搜索
5. 格式化为系统提示注入
```

### 1.4 数据结构

```python
@dataclass
class Memory:
    id: str                        # UUID 缩写 (8字符)
    type: MemoryType               # 7 种类型之一
    priority: MemoryPriority       # 4 种优先级之一
    content: str                   # 记忆内容
    source: str                    # conversation/task/manual
    tags: list[str]                # 标签列表
    created_at: datetime
    updated_at: datetime
    access_count: int              # 访问次数（用于热度排序）
    importance_score: float        # 0-1 重要性评分

class MemoryType(Enum):
    FACT = "fact"              # 事实信息
    PREFERENCE = "preference"  # 用户偏好
    SKILL = "skill"            # 成功模式
    ERROR = "error"            # 错误教训
    RULE = "rule"              # 规则约束
    CONTEXT = "context"        # 上下文信息
    PERSONA_TRAIT = "persona_trait"  # 人格特质

class MemoryPriority(Enum):
    TRANSIENT = "transient"    # 1天后删除
    SHORT_TERM = "short_term"  # 3天后删除
    LONG_TERM = "long_term"    # 数周
    PERMANENT = "permanent"    # 永不删除
```

### 1.5 存储机制

| 存储层 | 文件位置 | 格式 | 用途 |
|-------|---------|------|------|
| 主存储 | `data/memory/memories.json` | JSON | 完整记忆库 |
| 向量索引 | `data/memory/chromadb/` | SQLite + HNSW | 语义搜索 |
| 精华摘要 | `identity/MEMORY.md` | Markdown | 每次注入 |
| 对话历史 | `data/memory/conversation_history/*.jsonl` | JSONL | 原始记录 |
| 每日摘要 | `data/memory/daily_summaries/*.json` | JSON | 批量归纳 |

### 1.6 当前问题分析

| 问题 | 描述 | 影响 |
|-----|------|------|
| **过度记录** | AI 自动提取大量"用户偏好"，对企业用户无意义 | 存储/计算浪费 |
| **向量依赖** | 强依赖 ChromaDB 和 embedding 模型 | 部署复杂度高 |
| **个人化设计** | PREFERENCE/PERSONA_TRAIT 类型对企业无意义 | 代码冗余 |
| **每日归纳** | 凌晨定时任务对企业场景不适用 | 资源浪费 |
| **无限增长** | 记忆只增不减（除过期清理） | 长期性能下降 |

---

## 二、企业应用场景特点分析

### 2.1 与 C 端用户的核心差异

| 维度 | C 端用户 | 企业应用 |
|-----|---------|---------|
| **用户关系** | 长期服务同一用户 | 每次可能是不同用户/租户 |
| **记忆价值** | 用户偏好、习惯、历史 | 任务上下文、业务规则 |
| **记忆时长** | 永久（用户回归时恢复） | 任务结束即可丢弃 |
| **个性化需求** | 高（个性化体验） | 低（统一服务标准） |
| **隐私要求** | 用户同意即可 | 严格数据隔离、合规 |
| **规模** | 单用户记忆 | 多租户、大规模并发 |

### 2.2 企业场景的真实需求

```
企业 Agent 的核心目标：高效完成明确任务
```

**需要记住的：**
- 业务规则和约束（系统级，永久）
- 当前任务的上下文（任务级，临时）
- 常用 API/工具的使用模式（技能级，中期）
- 错误处理经验（规则级，永久）

**不需要记住的：**
- 用户偏好（每次可能是不同用户）
- 人格特质（不需要个性化）
- 闲聊内容（纯任务导向）
- 历史会话（隐私/合规要求）

### 2.3 企业场景的约束条件

1. **多租户隔离**：不同租户的记忆不能混淆
2. **合规要求**：敏感数据不能长期存储
3. **资源效率**：大规模部署时资源受限
4. **可观测性**：需要审计记忆使用情况
5. **可控性**：管理员可干预记忆内容

---

## 三、企业级 Memory 重构方案

### 3.1 方案概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Enterprise Memory                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ System Rules│  │ Task Context│  │ Skill Cache │         │
│  │  (Permanent)│  │  (Ephemeral)│  │   (TTL-based)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                  │
│                   ┌──────▼──────┐                          │
│                   │ Memory Router│                          │
│                   └──────┬──────┘                          │
│                          │                                  │
│         ┌────────────────┼────────────────┐                │
│         ▼                ▼                ▼                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Rule Store  │  │ Session Store│  │ Skill Store │        │
│  │ (ConfigMap) │  │ (Redis/Dict) │  │  (Optional) │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 三层存储设计

#### Layer 1: System Rules（系统规则层）

**特点：**
- 永久存储，不随任务变化
- 管理员配置，不可由 AI 修改
- 任务无关的业务约束

**数据结构：**
```python
@dataclass
class SystemRule:
    id: str
    category: RuleCategory  # COMPLIANCE / SECURITY / BUSINESS / CUSTOM
    content: str
    priority: int           # 1-10, 越高越重要
    enabled: bool
    created_by: str         # 管理员 ID
    created_at: datetime

class RuleCategory(Enum):
    COMPLIANCE = "compliance"    # 合规约束（如：不能存储 PII）
    SECURITY = "security"        # 安全约束（如：不能执行危险命令）
    BUSINESS = "business"        # 业务规则（如：审批流程）
    CUSTOM = "custom"            # 自定义规则
```

**存储方式：**
- 本地：YAML/JSON 配置文件
- 云端：Kubernetes ConfigMap / 数据库配置表

**示例配置：**
```yaml
# rules.yaml
rules:
  - id: "rule-001"
    category: "compliance"
    content: "不允许存储用户的身份证号、银行卡号等敏感信息"
    priority: 10
    enabled: true

  - id: "rule-002"
    category: "security"
    content: "禁止执行 rm -rf / 或类似的危险命令"
    priority: 10
    enabled: true

  - id: "rule-003"
    category: "business"
    content: "涉及金额超过 10000 元的操作需要二次确认"
    priority: 8
    enabled: true
```

#### Layer 2: Task Context（任务上下文层）

**特点：**
- 任务级生命周期，任务结束即销毁
- 按任务/会话隔离
- 轻量级，不使用向量搜索

**数据结构：**
```python
@dataclass
class TaskContext:
    task_id: str
    session_id: str
    tenant_id: str

    # 任务定义
    task_type: str          # predefined task type
    task_description: str

    # 累积上下文
    variables: dict         # 任务中提取的变量
    artifacts: list[str]    # 生成的工件引用
    checkpoints: list[Checkpoint]  # 关键节点

    # 执行状态
    current_step: int
    completed_steps: list[str]
    errors: list[ErrorRecord]

    created_at: datetime
    expires_at: datetime    # TTL 过期时间

@dataclass
class Checkpoint:
    step_id: str
    step_name: str
    summary: str            # 步骤完成摘要（100字内）
    timestamp: datetime
    variables_snapshot: dict  # 关键变量快照

@dataclass
class ErrorRecord:
    step_id: str
    error_type: str
    error_message: str
    retry_count: int
    resolution: str | None  # 如何解决的
```

**存储方式：**
- 推荐：Redis（带 TTL）或内存 Dict
- 备选：SQLite（任务结束后清理）

**接口设计：**
```python
class TaskContextManager:
    def create_context(self, task_id: str, tenant_id: str) -> TaskContext

    def get_context(self, task_id: str) -> TaskContext | None

    def update_context(self, task_id: str, updates: dict) -> None

    def add_checkpoint(self, task_id: str, checkpoint: Checkpoint) -> None

    def record_error(self, task_id: str, error: ErrorRecord) -> None

    def get_injection_context(self, task_id: str) -> str  # 返回格式化的上下文字符串

    def expire_context(self, task_id: str) -> None  # 立即过期
```

#### Layer 3: Skill Cache（技能缓存层）

**特点：**
- 可选层，用于缓存常用操作模式
- TTL 过期，定期刷新
- 不强依赖向量搜索

**数据结构：**
```python
@dataclass
class Skill:
    id: str
    name: str
    description: str
    category: SkillCategory

    # 技能内容
    pattern: str            # 识别模式（关键词或正则）
    template: str           # 执行模板
    examples: list[str]     # 使用示例

    # 元数据
    success_count: int      # 成功次数
    last_used: datetime
    ttl_days: int           # 过期天数

class SkillCategory(Enum):
    API_CALL = "api_call"       # API 调用模式
    DATA_TRANSFORM = "data_transform"  # 数据转换
    ERROR_HANDLING = "error_handling"  # 错误处理
    WORKFLOW = "workflow"       # 工作流模式
```

**存储方式：**
- SQLite 或 JSON 文件
- 可选向量索引（仅对 description 做 embedding）

### 3.3 简化的 Memory 类型

**移除的类型：**
- `PREFERENCE` - 企业不需要用户偏好
- `PERSONA_TRAIT` - 不需要个性化
- `CONTEXT` - 被 TaskContext 替代

**保留/新增的类型：**
```python
class EnterpriseMemoryType(Enum):
    # 保留
    FACT = "fact"          # 业务事实（如：API endpoint）
    SKILL = "skill"        # 操作技能（如：批量导入流程）
    ERROR = "error"        # 错误处理（如：某错误如何解决）
    RULE = "rule"          # 业务规则（从 System Rules 同步）

    # 新增
    API_SCHEMA = "api_schema"  # API 定义缓存
    TEMPLATE = "template"      # 常用模板
```

### 3.4 Memory Router 设计

```python
class EnterpriseMemoryRouter:
    """
    企业级记忆路由器
    根据请求类型路由到不同的存储层
    """

    def __init__(self, config: EnterpriseMemoryConfig):
        self.rule_store = SystemRuleStore(config.rules_path)
        self.context_store = TaskContextStore(config.context_backend)
        self.skill_store = SkillStore(config.skill_path)

    async def get_injection_context(
        self,
        task_id: str,
        task_type: str,
        query: str
    ) -> str:
        """
        获取注入到系统提示的上下文
        """
        parts = []

        # 1. 系统规则（总是注入）
        rules = self.rule_store.get_enabled_rules()
        parts.append(self._format_rules(rules))

        # 2. 任务上下文（按任务 ID 获取）
        context = self.context_store.get_context(task_id)
        if context:
            parts.append(self._format_context(context))

        # 3. 技能缓存（按任务类型匹配）
        skills = self.skill_store.get_skills_for_task(task_type)
        if skills:
            parts.append(self._format_skills(skills))

        return "\n\n".join(parts)

    def record_step_completion(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict
    ) -> None:
        """记录步骤完成（替代 AI 自动提取）"""
        self.context_store.add_checkpoint(task_id, Checkpoint(
            step_id=step_id,
            step_name=step_name,
            summary=summary,
            timestamp=datetime.now(),
            variables_snapshot=variables
        ))

    def record_error(
        self,
        task_id: str,
        step_id: str,
        error_type: str,
        error_message: str,
        resolution: str | None = None
    ) -> None:
        """记录错误（简化版，不做 AI 提取）"""
        self.context_store.record_error(task_id, ErrorRecord(
            step_id=step_id,
            error_type=error_type,
            error_message=error_message,
            retry_count=0,
            resolution=resolution
        ))
```

### 3.5 与现有系统的对比

| 维度 | 现有系统（C 端） | 重构后（企业） |
|-----|----------------|---------------|
| **记忆类型** | 7 种，含 PREFERENCE | 4-6 种，任务导向 |
| **存储后端** | ChromaDB（必需） | 多后端可选 |
| **向量搜索** | 强依赖 | 可选（仅 Skill 层） |
| **AI 提取** | 每轮对话调用 LLM | 无（规则写入） |
| **生命周期** | 永久 + 过期清理 | 任务级 TTL |
| **多租户** | 无 | 原生支持 |
| **部署复杂度** | 高（embedding 模型） | 低（纯文本配置） |
| **存储增长** | 无限增长 | 可控（TTL 自动清理） |

---

## 四、迁移方案

### 4.1 兼容性设计

```python
class MemoryBackend(Protocol):
    """抽象后端接口，支持多种实现"""

    async def get_injection_context(self, task_id: str, query: str) -> str: ...
    async def record_step(self, task_id: str, step_info: dict) -> None: ...
    async def record_error(self, task_id: str, error_info: dict) -> None: ...

class LegacyMemoryBackend(MemoryBackend):
    """兼容现有系统的适配器"""
    def __init__(self, memory_manager: MemoryManager):
        self.mm = memory_manager

    async def get_injection_context(self, task_id: str, query: str) -> str:
        return await self.mm.get_injection_context_async(query)

class EnterpriseMemoryBackend(MemoryBackend):
    """企业级实现"""
    def __init__(self, router: EnterpriseMemoryRouter):
        self.router = router

    async def get_injection_context(self, task_id: str, query: str) -> str:
        return self.router.get_injection_context(task_id, query)
```

### 4.2 配置切换

```python
# config.py
class MemoryConfig:
    backend: Literal["legacy", "enterprise"] = "legacy"

    # Legacy 配置
    legacy_data_dir: str = "data/memory"
    use_vector_search: bool = True

    # Enterprise 配置
    enterprise_rules_path: str = "config/rules.yaml"
    enterprise_context_backend: Literal["memory", "redis", "sqlite"] = "memory"
    enterprise_context_ttl_seconds: int = 3600  # 1 小时

# 初始化
def create_memory_backend(config: MemoryConfig) -> MemoryBackend:
    if config.backend == "legacy":
        return LegacyMemoryBackend(MemoryManager(...))
    else:
        return EnterpriseMemoryBackend(EnterpriseMemoryRouter(...))
```

### 4.3 迁移步骤

1. **Phase 1：抽象接口**
   - 定义 `MemoryBackend` 协议
   - 将现有代码封装为 `LegacyMemoryBackend`

2. **Phase 2：实现企业版**
   - 实现 `EnterpriseMemoryRouter`
   - 实现三层存储组件

3. **Phase 3：灰度切换**
   - 通过配置选择 backend
   - 新租户使用企业版，老租户保持兼容

4. **Phase 4：完全迁移**
   - 移除 Legacy 依赖
   - 简化代码

---

## 五、代码结构建议

```
src/openakita/memory/
├── __init__.py
├── protocol.py           # MemoryBackend 协议定义
│
├── legacy/               # 现有系统（保持不变）
│   ├── manager.py
│   ├── vector_store.py
│   ├── extractor.py
│   ├── daily_consolidator.py
│   └── types.py
│
├── enterprise/           # 企业级实现（新增）
│   ├── __init__.py
│   ├── router.py         # EnterpriseMemoryRouter
│   ├── rules.py          # SystemRuleStore
│   ├── context.py        # TaskContextStore
│   ├── skills.py         # SkillStore
│   └── types.py          # Enterprise 类型定义
│
└── backends/
    ├── __init__.py
    ├── legacy_adapter.py # LegacyMemoryBackend
    └── enterprise_backend.py  # EnterpriseMemoryBackend
```

---

## 六、性能与资源对比

| 指标 | Legacy | Enterprise |
|-----|--------|------------|
| **启动时间** | 5-10s（加载 embedding） | <100ms |
| **单次查询延迟** | ~50ms（向量搜索） | ~5ms（字典查询） |
| **内存占用** | 200-500MB（embedding 模型） | 10-50MB |
| **存储增长** | 无限 | 可控（TTL） |
| **依赖** | ChromaDB, sentence-transformers | 无强制依赖 |

---

## 七、总结

企业级 Memory 重构的核心思想：

1. **任务导向**：记忆服务于任务，不是为了个性化
2. **简化架构**：移除向量搜索依赖，使用轻量存储
3. **生命周期管理**：任务结束即清理，避免无限增长
4. **多租户隔离**：每个任务/租户独立上下文
5. **可配置性**：系统规则可由管理员配置，AI 不可修改

这套方案可以显著降低部署复杂度和资源消耗，同时更适合企业应用的任务导向特点。
