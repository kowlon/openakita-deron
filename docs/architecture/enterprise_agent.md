# OpenAkita Enterprise Agent Architecture

This document provides a comprehensive overview of the OpenAkita Enterprise Self-Evolving Agent architecture.

## Overview

OpenAkita is an enterprise-grade AI agent with three core capabilities:

1. **Intelligent Context Management** - Multi-layer context with token budget control
2. **Unified Capability System** - Seamless integration of Tools, Skills, and MCP
3. **Self-Evolution** - Automatic learning and improvement from execution experience

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OpenAkita Enterprise Agent                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                         User Interface Layer                          │   │
│   │   CLI │ Telegram │ DingTalk │ Feishu │ WeWork │ Desktop │ Web UI    │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                         Channel Gateway                                │   │
│   │                    (Message routing & normalization)                   │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                           Agent Core                                   │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│   │  │   Identity  │  │    Brain    │  │  Ralph Loop │  │   Session   │  │   │
│   │  │   System    │  │   (LLM)     │  │  (ReAct)    │  │   Manager   │  │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    Enterprise Context Layer                            │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│   │  │                    ContextOrchestrator                            │ │   │
│   │  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────────┐ │ │   │
│   │  │  │  System    │  │   Task     │  │     Conversation           │ │ │   │
│   │  │  │  Context   │  │  Context   │  │     Context                │ │ │   │
│   │  │  │ (Permanent)│  │  (Task)    │  │    (Session)               │ │ │   │
│   │  │  └────────────┘  └────────────┘  └────────────────────────────┘ │ │   │
│   │  │  ┌────────────────────────────────────────────────────────────┐ │ │   │
│   │  │  │              BudgetController + Compressor                  │ │ │   │
│   │  │  └────────────────────────────────────────────────────────────┘ │ │   │
│   │  └─────────────────────────────────────────────────────────────────┘ │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    Unified Capability Layer                            │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│   │  │                    CapabilityExecutor                             │ │   │
│   │  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────────┐ │ │   │
│   │  │  │    Tool    │  │   Skill    │  │           MCP               │ │ │   │
│   │  │  │  Adapter   │  │  Adapter   │  │        Adapter              │ │ │   │
│   │  │  └────────────┘  └────────────┘  └────────────────────────────┘ │ │   │
│   │  │  ┌────────────────────────────────────────────────────────────┐ │ │   │
│   │  │  │                    CapabilityRegistry                       │ │ │   │
│   │  │  └────────────────────────────────────────────────────────────┘ │ │   │
│   │  └─────────────────────────────────────────────────────────────────┘ │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                      Self-Evolution Layer                              │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│   │  │                   EvolutionOrchestrator                           │ │   │
│   │  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────────┐ │ │   │
│   │  │  │ Experience │  │  Pattern   │  │       Skill                │ │ │   │
│   │  │  │   Store    │→│ Extractor  │→│       Evolver              │ │ │   │
│   │  │  └────────────┘  └────────────┘  └────────────────────────────┘ │ │   │
│   │  │                         ↓                                        │ │   │
│   │  │  ┌────────────────────────────────────────────────────────────┐ │ │   │
│   │  │  │                   ProposalGenerator                          │ │ │   │
│   │  │  └────────────────────────────────────────────────────────────┘ │ │   │
│   │  └─────────────────────────────────────────────────────────────────┘ │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                        Storage Layer                                   │   │
│   │     SQLite │ Sessions │ Vector Store │ File System │ Cache          │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Context Layer (Phase 1)

The Context Layer provides intelligent context management with token budget control.

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ContextOrchestrator                       │
│                    (Context Orchestrator)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │  SystemContext   │  │   TaskContext    │  │ Conversation│ │
│  │   (Permanent)    │  │   (Task)         │  │ Context    │ │
│  │                  │  │                  │  │ (Session)   │ │
│  │ - identity       │  │ - task_id        │  │ - messages │ │
│  │ - rules          │  │ - description    │  │ - max_rounds│ │
│  │ - capabilities   │  │ - step_summaries │  │ - max_tokens│ │
│  │ - policies       │  │ - variables      │  │            │ │
│  │                  │  │ - checkpoints    │  │            │ │
│  └──────────────────┘  └──────────────────┘  └────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              BudgetController (Budget Controller)     │   │
│  │              - Dynamic token budget allocation        │   │
│  │              - Warning mechanism (75%/90%)            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              ContextCompressor (Compressor)           │   │
│  │              - sliding_window strategy                │   │
│  │              - priority strategy                      │   │
│  │              - hybrid strategy                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### Three-Layer Context Model

| Layer | Class | Purpose | Lifetime |
|-------|-------|---------|----------|
| Permanent | `SystemContext` | Identity, rules, capabilities | Application lifetime |
| Task | `TaskContext` | Goals, progress, variables | Task duration |
| Session | `ConversationContext` | Messages, token budget | Session duration |

#### Key Components

**SystemContext**
```python
from openakita.context import ISystemContext

class SystemContext(ISystemContext):
    """Permanent context layer - survives across sessions"""

    identity: str              # Agent identity
    rules: list[str]           # Behavioral rules
    capabilities_manifest: str # Available capabilities
    policies: dict[str, Any]   # Policy configurations

    def to_prompt(self) -> str:
        """Generate system prompt section"""
```

**TaskContext**
```python
from openakita.context import ITaskContext

class TaskContext(ITaskContext):
    """Task context layer - per-task state"""

    task_id: str
    description: str
    step_summaries: list[str]
    variables: dict[str, Any]
    checkpoints: list[dict]

    def add_step_summary(self, step_name: str, summary: str) -> None
    def save_checkpoint(self, state: dict) -> str
    def rollback(self, checkpoint_id: str) -> dict | None
```

**ConversationContext**
```python
from openakita.context import IConversationContext

class ConversationContext(IConversationContext):
    """Session context layer - conversation history"""

    messages: list[dict]
    max_rounds: int
    max_tokens: int

    def add_message(self, role: str, content: str | list) -> None
    def to_messages(self) -> list[dict]
    def estimate_tokens(self) -> int
```

**BudgetController**
```python
from openakita.context import BudgetController, BudgetCheckResult

controller = BudgetController(
    total_budget=128000,
    warning_threshold=0.75,
    critical_threshold=0.90
)

result: BudgetCheckResult = controller.check_budget(
    system_tokens=1000,
    task_tokens=500,
    conversation_tokens=8000
)

# result.status: "ok" | "warning" | "critical"
# result.should_compress: bool
# result.target_tokens: int
```

#### Context Priority

```python
from openakita.context import ContextPriority

class ContextPriority(Enum):
    CRITICAL = 0   # System-level, cannot be trimmed
    HIGH = 1       # Important task context
    MEDIUM = 2     # Regular conversation
    LOW = 3        # Historical context, first to trim
```

When context exceeds budget, lower priority content is trimmed first:
`CRITICAL > HIGH > MEDIUM > LOW`

---

### 2. Capability Layer (Phase 2)

The Capability Layer provides unified access to Tools, Skills, and MCP.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CapabilityExecutor                            │
│                    (Unified Executor)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   CapabilityRegistry                       │   │
│  │                   (Capability Registry)                    │   │
│  │   - Register/unregister capabilities                       │   │
│  │   - Index by type/tags                                    │   │
│  │   - Search and discovery                                  │   │
│  │   - Generate system prompt manifest                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ ToolAdapter  │ │ SkillAdapter │ │  MCPAdapter  │             │
│  │ (Tool)       │ │ (Skill)      │ │ (MCP)        │             │
│  ├──────────────┤ ├──────────────┤ ├──────────────┤             │
│  │ - read_file  │ │ - /commit    │ │ - browser    │             │
│  │ - write_file │ │ - /review    │ │ - search     │             │
│  │ - shell      │ │ - /pr        │ │ - database   │             │
│  │ - web        │ │ - ...        │ │ - ...        │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
│          ^                ^                ^                     │
│          │                │                │                     │
│  ┌───────┴────────┐ ┌─────┴──────┐ ┌──────┴───────┐             │
│  │ ToolCatalog    │ │SkillManager│ │ MCPManager   │             │
│  │ ToolExecutor   │ │            │ │ MCPCatalog   │             │
│  └────────────────┘ └────────────┘ └──────────────┘             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   CapabilityAdapter (Base)                 │   │
│  │   - load() / reload()                                     │   │
│  │   - execute()                                              │   │
│  │   - has_capability() / get_capability()                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

#### Capability Types

```python
from openakita.capability import CapabilityType, CapabilityMeta

class CapabilityType(Enum):
    TOOL = "tool"        # System tools (file, shell, web)
    SKILL = "skill"      # Skills (/commit, /review, etc.)
    MCP = "mcp"          # MCP tools
    BUILTIN = "builtin"  # Built-in capabilities
```

#### Capability Metadata

```python
@dataclass
class CapabilityMeta:
    name: str                           # Capability name
    type: CapabilityType                # Capability type
    description: str                    # Description
    parameters: dict | None             # JSON Schema parameters
    status: CapabilityStatus            # Status
    tags: list[str]                     # Tags for categorization
    priority: int                       # Priority for execution
    usage_stats: CapabilityUsageStats   # Usage statistics
```

#### Capability Execution Flow

```
User Request (LLM returns tool_use)
    |
    v
Agent.capability_executor.execute(name, params)
    |
    +-- 1. Find adapter (by hint or registry lookup)
    |
    +-- 2. Call adapter execute
    |       |
    |       +-- ToolAdapter.execute(name, params)
    |       |       +-- ToolExecutor.run(name, params)
    |       |
    |       +-- SkillAdapter.execute(name, params)
    |       |       +-- SkillManager.invoke_skill(name, params)
    |       |
    |       +-- MCPAdapter.execute(name, params)
    |               +-- MCPClient.call_tool(name, params)
    |
    +-- 3. Return ExecutionResult
            |
            v
        Agent processes result
```

#### Usage Example

```python
from openakita.capability import CapabilityExecutor, CapabilityRegistry

# Create registry and executor
registry = CapabilityRegistry()
executor = CapabilityExecutor(registry)

# Register adapters
executor.register_adapter("tools", tool_adapter)
executor.register_adapter("skills", skill_adapter)
executor.register_adapter("mcp", mcp_adapter)

# Execute capability
result = await executor.execute("read_file", {"path": "/tmp/test.txt"})

# result.success: bool
# result.output: Any
# result.error: str | None
# result.duration_ms: float
```

---

### 3. Evolution Layer (Phase 3)

The Evolution Layer enables automatic learning and improvement.

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   EvolutionOrchestrator                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Collect    │->│  Analyze    │->│  Evolve     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│        v                v                v                   │
│  ExperienceStore  PatternExtractor  SkillEvolver            │
│                                        ^                     │
│                               ProposalGenerator              │
└─────────────────────────────────────────────────────────────┘
```

#### Data Flow

```
Task Execution -> ExecutionTrace -> ExperienceStore
                                        |
                                        v
                                PatternExtractor
                                        |
                                        v
                                EvolutionProposal
                                        |
                                        v
                                SkillEvolver
                                        |
                                        v
                                EvolutionResult
```

#### Core Models

```python
from openakita.evolution import (
    ExecutionTrace,
    ExecutionStep,
    ExecutionStatus,
    PatternObservation,
    EvolutionProposal
)

@dataclass
class ExecutionTrace:
    """Record of a complete task execution"""
    trace_id: str
    task_id: str
    session_id: str
    task_description: str
    steps: list[ExecutionStep]
    outcome: ExecutionStatus
    capabilities_used: list[str]
    started_at: datetime
    completed_at: datetime

@dataclass
class ExecutionStep:
    """Single step in execution"""
    step_id: str
    step_type: StepType
    action: str
    input_data: dict
    output_data: dict | None
    outcome: ExecutionStatus
    duration_ms: float

@dataclass
class EvolutionProposal:
    """Proposed improvement"""
    proposal_id: str
    proposal_type: str  # "new_skill", "improve_skill", "update_flow"
    description: str
    rationale: str
    priority: int
    auto_approved: bool
```

#### Evolution Cycle

```python
from openakita.evolution import EvolutionOrchestrator

orchestrator = EvolutionOrchestrator(
    min_traces_for_evolution=10,
    evolution_interval_hours=24
)

# Record execution
trace_id = orchestrator.record_execution(
    task_id="task-123",
    session_id="session-456",
    task_description="Write a Python function",
    outcome="success",
    capabilities_used=["shell", "write_file"]
)

# Check if evolution should run
if orchestrator.should_evolve():
    result = orchestrator.run_evolution_cycle()
    print(f"Patterns found: {result['patterns_found']}")
    print(f"Proposals generated: {result['proposals_generated']}")
```

#### Pattern Types

The PatternExtractor identifies:

| Pattern Type | Description |
|--------------|-------------|
| Success Patterns | Repeated capability combinations that lead to success |
| Failure Patterns | Common error sequences and problematic capabilities |
| Capability Patterns | Reliable capabilities and effective pairings |
| Performance Patterns | Slow capabilities and optimization opportunities |

---

## Agent Core

### Agent Initialization

```python
from openakita.core.agent import Agent

agent = Agent(
    config=config,
    llm_client=llm_client,
    tool_catalog=tool_catalog,
    skill_manager=skill_manager,
    mcp_client=mcp_client
)

# Agent automatically initializes:
# - context_manager (EnterpriseContextManager)
# - capability_registry (CapabilityRegistry)
# - capability_executor (CapabilityExecutor)
# - evolution_orchestrator (EvolutionOrchestrator)
```

### Agent Attributes

```python
class Agent:
    # Context management
    context_manager: EnterpriseContextManager
    context_backend: ContextBackend

    # Capability system
    capability_registry: CapabilityRegistry
    capability_executor: CapabilityExecutor

    # Evolution system
    evolution_orchestrator: EvolutionOrchestrator

    # Core components
    brain: Brain                    # LLM interaction
    tool_catalog: ToolCatalog       # Tool definitions
    tool_executor: ToolExecutor     # Tool execution
    skill_manager: SkillManager     # Skill management
    mcp_client: MCPClient           # MCP client
```

### Ralph Loop (ReAct Engine)

The Ralph Loop implements the "Never Give Up" philosophy:

```
while not task_complete:
    result = execute_step()
    if result.failed:
        analyze_failure()
        if can_fix_locally:
            apply_fix()
        else:
            search_github_for_solution()
            if found:
                install_and_retry()
            else:
                generate_solution()
    verify_progress()
    save_to_memory()
```

---

## Data Flow

### Message Processing Flow

```
1. User sends message via channel
2. Channel adapter normalizes message
3. Media preprocessing:
   - Voice: Download -> Whisper transcription -> Text
   - Image: Download -> Base64 encode -> Multimodal input
4. Session manager retrieves/creates context
5. Prompt Compiler (Stage 1) structures the request
6. Brain (Stage 2) processes with tools available
7. Ralph loop ensures completion
8. Response recorded to session history
9. Evolution system records execution trace
10. Response sent back through channel
```

### Context Building Flow

```
User Request
    |
    v
EnterpriseContextManager.build_context(task_id, session_id)
    |
    v
ContextOrchestrator.build_context()
    |
    +-- 1. Get SystemContext.to_prompt()
    |
    +-- 2. Get TaskContext.to_prompt()
    |
    +-- 3. Get ConversationContext.to_messages()
    |
    +-- 4. BudgetController.check_budget()
    |       +-- If exceeded -> ContextCompressor.compress()
    |
    +-- 5. Return (system_prompt, messages)
            |
            v
        LLM API call
```

---

## Configuration

### Context Configuration

```python
from openakita.context import ContextConfig, TokenBudget

context_config = ContextConfig(
    max_conversation_rounds=20,   # Max conversation rounds
    max_task_summaries=50,         # Max task summaries
    max_task_variables=100,        # Max task variables
    max_conversation_tokens=8000,  # Max tokens for conversation
    max_task_tokens=4000,          # Max tokens for task
)

token_budget = TokenBudget(
    total=128000,           # Total token budget
    system_reserve=16000,   # System layer reserve
    task_reserve=8000,      # Task layer reserve
    conversation_reserve=32000,  # Conversation reserve
    response_reserve=16000, # Response reserve
    buffer=8000,            # Buffer space
)
```

### Evolution Configuration

```python
from openakita.evolution import OrchestratorConfig

evolution_config = OrchestratorConfig(
    min_traces_for_evolution=10,    # Minimum traces before evolution
    evolution_interval_hours=24,    # Hours between evolution cycles
    auto_approve_threshold=0.9,     # Auto-approve confidence threshold
    max_proposals_per_cycle=5,      # Max proposals per cycle
    persist_path="/data/evolution", # Optional persistence path
)
```

---

## Performance

### Performance Thresholds

#### Context Layer

| Operation | Threshold (ms) | Description |
|-----------|----------------|-------------|
| Initialization | < 10 | EnterpriseContextManager init |
| Context Build | < 20 | build_context() method |
| Add Message | < 5 | add_message() method |
| Large Scale | < 1000 | 1000 operations total |

#### Capability Layer

| Operation | Threshold (ms) | Description |
|-----------|----------------|-------------|
| Batch Register | < 100 | Register 100 capabilities |
| Search | < 10 | Single search query |
| Execute | < 5 | Single capability execution |
| Manifest Gen | < 100 | generate_manifest() method |

#### Evolution Layer

| Operation | Threshold (ms) | Description |
|-----------|----------------|-------------|
| Trace Storage | < 5 | Single ExecutionTrace store |
| Pattern Extract | < 500 | extract_patterns() method |
| Complex Query | < 50 | query() method |
| Evolution Cycle | < 1000 | run_evolution_cycle() method |

### Memory Usage

| Scenario | Memory Usage | Description |
|----------|--------------|-------------|
| Empty Manager | ~1KB | Initial state |
| 10 Tasks | ~5KB | ~500B per task |
| 100 Messages | ~20KB | Sliding window controlled |
| 20 Rounds | ~50KB | Including context metadata |

---

## Testing

### Test Structure

```
tests/
├── unit/                        # Unit tests
│   ├── test_context/
│   ├── test_capability/
│   └── test_evolution/
├── integration/                 # Integration tests
│   └── test_context_switching.py
├── e2e/                         # End-to-end tests
│   ├── test_e2e_context.py
│   ├── test_e2e_capability.py
│   └── test_e2e_evolution.py
└── benchmark/                   # Performance tests
    └── test_performance.py
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific layer tests
pytest tests/unit/test_context/ -v
pytest tests/unit/test_capability/ -v
pytest tests/unit/test_evolution/ -v

# Run E2E tests
pytest tests/e2e/ -v

# Run performance benchmarks
pytest tests/benchmark/ -v
```

---

## Module Reference

### Context Module

```python
from openakita.context import (
    # Factory
    create_context_backend,
    create_orchestrator,
    # Protocol
    ContextBackend,
    # Config
    TokenBudget,
    ContextConfig,
    # Budget Controller
    BudgetController,
    BudgetAllocation,
    BudgetCheckResult,
    BudgetState,
    # Orchestrator
    ContextOrchestrator,
    # Interfaces
    IContext,
    ISystemContext,
    ITaskContext,
    IConversationContext,
    ICompressor,
    IContextOrchestrator,
    # Enums
    ContextPriority,
    CompressionStrategy,
    # Exceptions
    ContextError,
    TokenBudgetExceeded,
)
```

### Capability Module

```python
from openakita.capability import (
    # Types
    CapabilityType,
    CapabilityStatus,
    CapabilityMeta,
    CapabilityCategory,
    # Registry
    CapabilityRegistry,
    get_global_registry,
    reset_global_registry,
    # Executor
    CapabilityExecutor,
    MockCapabilityExecutor,
    ExecutorStats,
)
```

### Evolution Module

```python
from openakita.evolution import (
    # Legacy
    NeedAnalyzer,
    AutoInstaller,
    SkillGenerator,
    SelfChecker,
    LogAnalyzer,
    # Models
    ExecutionStatus,
    StepType,
    OutcomeLabel,
    ExecutionStep,
    ExecutionTrace,
    PatternObservation,
    EvolutionProposal,
    # Store
    StoreConfig,
    ExperienceStore,
    MockExperienceStore,
    # Pattern Extraction
    PatternConfig,
    PatternExtractor,
    # Proposal Generation
    ProposalConfig,
    ProposalGenerator,
    # Skill Evolution
    EvolverConfig,
    SkillEvolver,
    EvolutionResult,
    # Orchestrator
    OrchestratorConfig,
    EvolutionOrchestrator,
)
```

---

## Extension Guide

### Adding a New Capability Adapter

```python
from openakita.capability import CapabilityAdapter, CapabilityMeta, CapabilityType

class MyCustomAdapter(CapabilityAdapter):
    def __init__(self, source: str = "custom"):
        super().__init__(source)
        self._capabilities: dict[str, CapabilityMeta] = {}

    def load(self) -> list[CapabilityMeta]:
        # Load capabilities from your source
        capabilities = [
            CapabilityMeta(
                name="my_capability",
                type=CapabilityType.BUILTIN,
                description="My custom capability",
                parameters={"type": "object", "properties": {...}},
                status=CapabilityStatus.AVAILABLE,
                tags=["custom"],
                priority=100,
            )
        ]
        for cap in capabilities:
            self._capabilities[cap.name] = cap
        return capabilities

    async def execute(self, name: str, params: dict) -> ExecutionResult:
        if name not in self._capabilities:
            return ExecutionResult(success=False, error="Unknown capability")

        # Execute the capability
        result = await self._do_execute(name, params)
        return ExecutionResult(success=True, output=result)

# Register with executor
executor.register_adapter("custom", MyCustomAdapter())
```

### Adding a New Context Strategy

```python
from openakita.context import ICompressor, CompressionStrategy

class MyCompressionStrategy(ICompressor):
    @property
    def strategy_name(self) -> str:
        return "my_strategy"

    def compress(
        self,
        messages: list[dict],
        target_tokens: int,
        priority: ContextPriority = ContextPriority.MEDIUM
    ) -> tuple[list[dict], CompressionReport]:
        # Implement your compression logic
        compressed = self._apply_custom_logic(messages, target_tokens)
        report = CompressionReport(
            original_count=len(messages),
            compressed_count=len(compressed),
            compression_ratio=len(compressed) / len(messages)
        )
        return compressed, report
```

---

## File Structure

```
src/openakita/
├── core/                    # Core agent logic
│   ├── agent.py             # Main Agent class
│   ├── brain.py             # LLM interaction
│   ├── ralph.py             # Ralph loop
│   ├── reasoning_engine.py  # ReAct engine
│   └── helpers/             # Helper modules
│       ├── capability_helper.py
│       ├── evolution_helper.py
│       └── session_helper.py
├── context/                 # Context management (Phase 1)
│   ├── __init__.py
│   ├── interfaces.py        # Abstract interfaces
│   ├── config.py            # Configuration
│   ├── exceptions.py        # Exceptions
│   ├── system_context.py    # Permanent layer
│   ├── task_context.py      # Task layer
│   ├── conversation_context.py  # Session layer
│   ├── orchestrator.py      # Context orchestrator
│   ├── budget_controller.py # Token budget
│   ├── compressor.py        # Compression strategies
│   ├── manager.py           # EnterpriseContextManager
│   └── protocol.py          # ContextBackend protocol
├── capability/              # Capability system (Phase 2)
│   ├── __init__.py
│   ├── types.py             # Type definitions
│   ├── registry.py          # Capability registry
│   ├── executor.py          # Unified executor
│   └── adapters/            # Capability adapters
│       ├── base.py          # Base adapter
│       ├── tool_adapter.py  # Tool adapter
│       ├── skill_adapter.py # Skill adapter
│       └── mcp_adapter.py   # MCP adapter
├── evolution/               # Self-evolution (Phase 3)
│   ├── __init__.py
│   ├── models.py            # Data models
│   ├── experience_store.py  # Execution storage
│   ├── pattern_extractor.py # Pattern analysis
│   ├── proposal_generator.py# Proposal generation
│   ├── skill_evolver.py     # Skill evolution
│   └── orchestrator.py      # Evolution orchestrator
├── tools/                   # Tool implementations
├── skills/                  # Skill system
├── channels/                # IM integrations
├── llm/                     # LLM providers
├── storage/                 # Persistence
├── sessions/                # Session management
└── testing/                 # Test framework
```

---

## Design Principles

### 1. Async-First

All I/O operations use `async/await`:

```python
async def process_message(self, message: str) -> str:
    response = await self.brain.think(messages)
    return response.content
```

### 2. Fail-Safe Execution

Tools have multiple safety layers:

```python
@safe_execute
@require_confirmation(dangerous=True)
@timeout(seconds=30)
async def run_shell_command(cmd: str) -> str:
    ...
```

### 3. Stateless with Persistence

- Each request is stateless
- State persisted to SQLite/files
- Fresh context loaded per request

### 4. Modular and Extensible

- Skills can be added dynamically
- Channels follow adapter pattern
- Tools implement common interface

### 5. Separation of Concerns

- Context management isolated in its own layer
- Capabilities abstracted through adapters
- Evolution operates independently

---

## Security Considerations

See [SECURITY.md](../../SECURITY.md) for detailed security information.

Key points:
- Command confirmation for dangerous operations
- Path restrictions for file access
- Input validation and sanitization
- Rate limiting on API calls
- Isolated execution environments for skills

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-27 | Complete architecture with all three phases |

---

## References

- [Phase 1: Context Layer Report](../refactor/context_layer_complete.md)
- [Phase 2: Capability Layer Report](../refactor/capability_layer_complete.md)
- [Phase 3: Evolution Layer Report](../refactor/evolution_layer_complete.md)
- [Performance Benchmark](../refactor/performance_benchmark.md)
- [Original Design Document](../refactor/20260226_enterprise_self_evolution_agent.md)

---

*This document was generated as part of TASK-305: Complete Architecture Documentation*