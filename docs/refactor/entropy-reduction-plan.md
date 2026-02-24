# OpenAkita 熵减方案设计

## 1. 背景与目标

### 1.1 背景
当前 OpenAkita 项目同时支持 C 端用户场景和企业级场景，包含大量用户端特定功能（活人感、人格系统、表情包等）。为了降低代码复杂度、提高维护效率，需要进行熵减，移除用户端特定功能，保留企业级核心功能。

### 1.2 目标
- 删除所有用户端特定功能代码
- 保留企业级核心功能
- 确保 webapp 功能完整可用
- 保持通道适配器核心通信能力
- 无破坏性变更，系统可正常运行

---

## 2. 功能分类

### 2.1 需要删除的用户端功能

| 模块 | 文件路径 | 功能描述 | 删除优先级 |
|------|----------|----------|------------|
| **活人感引擎** | `core/proactive.py` | 主动消息生成、问候、闲聊 | P0 |
| **人格系统** | `core/persona.py` | 三层人格管理、偏好维度 | P0 |
| **偏好挖掘** | `core/trait_miner.py` | 用户偏好分析和挖掘 | P0 |
| **用户档案** | `core/user_profile.py` | 用户信息收集和管理 | P0 |
| **表情包引擎** | `tools/sticker.py` | 表情包搜索和发送 | P0 |
| **人格处理器** | `tools/handlers/persona.py` | 人格相关工具处理 | P0 |
| **表情包处理器** | `tools/handlers/sticker.py` | 表情包工具处理 | P0 |
| **IM通道处理器** | `tools/handlers/im_channel.py` | IM通道工具处理（部分保留） | P1 |
| **用户档案处理器** | `tools/handlers/profile.py` | 用户档案工具处理 | P0 |
| **人格工具定义** | `tools/definitions/persona.py` | PERSONA_TOOLS | P0 |
| **表情包工具定义** | `tools/definitions/sticker.py` | STICKER_TOOLS | P0 |
| **用户档案工具定义** | `tools/definitions/profile.py` | PROFILE_TOOLS | P0 |
| **IM通道工具定义** | `tools/definitions/im_channel.py` | IM_CHANNEL_TOOLS（部分保留） | P1 |
| **人格预设目录** | `identity/personas/` | 人格预设文件 | P0 |
| **表情包数据** | `data/sticker/` | 表情包数据目录 | P0 |

### 2.2 需要保留的企业级功能

| 模块 | 文件路径 | 功能描述 | 保留原因 |
|------|----------|----------|----------|
| **记忆系统** | `memory/` | 企业级记忆管理 | 核心功能 |
| **上下文管理** | `context/` | 企业级上下文 | 核心功能 |
| **API服务** | `api/` | RESTful API | 企业级入口 |
| **核心引擎** | `core/brain.py` | LLM 调用封装 | 核心功能 |
| **Agent主逻辑** | `core/agent.py` | 主控制器（需修改） | 核心功能 |
| **推理引擎** | `core/reasoning_engine.py` | 推理逻辑 | 核心功能 |
| **工具执行器** | `core/tool_executor.py` | 工具执行 | 核心功能 |
| **技能系统** | `skills/` | 技能管理 | 企业级扩展 |
| **会话管理** | `sessions/` | 会话状态管理 | 核心功能 |
| **存储系统** | `storage/` | 数据持久化 | 核心功能 |
| **通道适配器** | `channels/` | IM平台对接 | 企业级通道 |
| **Web UI** | `seeagent-webui/` | 前端界面 | 企业级入口 |
| **LLM客户端** | `llm/` | LLM API 封装 | 核心功能 |
| **编排系统** | `orchestration/` | 多Agent编排 | 企业级特性 |

### 2.3 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `core/agent.py` | 移除用户端功能初始化和注册 |
| `config.py` | 移除用户端配置项 |
| `tools/definitions/__init__.py` | 从 BASE_TOOLS 移除用户端工具 |
| `tools/handlers/__init__.py` | 移除用户端 handler 注册 |
| `channels/adapters/*.py` | 移除 sticker 等用户端功能调用 |
| `memory/types.py` | 移除 PERSONA_TRAIT 类型 |

---

## 3. 详细删除计划

### 3.1 Phase 1: 配置清理（影响最小）

**目标**: 清理配置文件中的用户端配置项

**修改文件**: `src/openakita/config.py`

**删除配置项**:
```python
# 人格系统配置
persona_name: str = Field(default="default", ...)

# 活人感引擎配置
proactive_enabled: bool = Field(default=True, ...)
proactive_max_daily_messages: int = Field(default=3, ...)
proactive_min_interval_minutes: int = Field(default=120, ...)
proactive_quiet_hours_start: int = Field(default=23, ...)
proactive_quiet_hours_end: int = Field(default=7, ...)
proactive_idle_threshold_hours: int = Field(default=24, ...)

# 表情包配置
sticker_enabled: bool = Field(default=True, ...)
sticker_data_dir: str = Field(default="data/sticker", ...)
```

**相关路径属性**（删除）:
```python
@property
def personas_path(self) -> Path: ...

@property
def sticker_data_path(self) -> Path: ...
```

**运行时状态**（修改 _PERSISTABLE_KEYS）:
```python
# 移除:
"persona_name",
"proactive_enabled",
"proactive_max_daily_messages",
"proactive_min_interval_minutes",
"proactive_quiet_hours_start",
"proactive_quiet_hours_end",
```

### 3.2 Phase 2: 工具定义清理

**目标**: 从工具定义中移除用户端工具

**修改文件**:
1. `src/openakita/tools/definitions/__init__.py`
   ```python
   # 从 BASE_TOOLS 中移除:
   from .persona import PERSONA_TOOLS
   from .sticker import STICKER_TOOLS
   from .profile import PROFILE_TOOLS
   # IM_CHANNEL_TOOLS 部分保留（deliver_artifacts 等）
   ```

2. 删除工具定义文件:
   - `src/openakita/tools/definitions/persona.py`
   - `src/openakita/tools/definitions/sticker.py`
   - `src/openakita/tools/definitions/profile.py`
   - 修改 `src/openakita/tools/definitions/im_channel.py`（只保留核心工具）

**IM_CHANNEL_TOOLS 保留**:
```python
# 保留:
- deliver_artifacts  # 附件发送（企业级需要）
- get_voice_file     # 语音文件获取
- get_image_file     # 图片文件获取
- get_chat_history   # 聊天历史获取

# 删除:
- （无，IM通道工具都是核心功能）
```

### 3.3 Phase 3: Handler 清理

**目标**: 移除用户端功能的 Handler 实现

**删除文件**:
- `src/openakita/tools/handlers/persona.py`
- `src/openakita/tools/handlers/sticker.py`
- `src/openakita/tools/handlers/profile.py`

**修改文件**: `src/openakita/tools/handlers/__init__.py`
```python
# 移除导入和注册:
from .persona import create_handler as create_persona_handler
from .sticker import create_handler as create_sticker_handler
from .profile import create_handler as create_profile_handler
```

**保留**: `src/openakita/tools/handlers/im_channel.py`（核心通信功能）

### 3.4 Phase 4: 核心模块清理

**目标**: 移除用户端核心模块

**删除顺序**（按依赖关系）:
1. `core/trait_miner.py`（依赖 persona）
2. `core/proactive.py`（依赖 persona）
3. `core/persona.py`
4. `core/user_profile.py`
5. `tools/sticker.py`

**修改 agent.py**:
```python
# 删除导入:
from .persona import PersonaManager
from .proactive import ProactiveConfig, ProactiveEngine
from .trait_miner import TraitMiner
from ..tools.sticker import StickerEngine
from .user_profile import get_profile_manager

# 删除 Handler 导入:
from ..tools.handlers.persona import create_handler as create_persona_handler
from ..tools.handlers.sticker import create_handler as create_sticker_handler
from ..tools.handlers.profile import create_handler as create_profile_handler

# 删除初始化代码（约30-50行）:
self.persona_manager = PersonaManager(...)
self.trait_miner = TraitMiner(...)
self.proactive_engine = ProactiveEngine(...)
self.sticker_engine = StickerEngine(...)

# 删除 Handler 注册:
self.handler_registry.register("persona", create_persona_handler(self))
self.handler_registry.register("sticker", create_sticker_handler(self))
self.handler_registry.register("profile", create_profile_handler(self))

# 删除运行时状态相关:
from ..config import runtime_state
runtime_state.load()
```

### 3.5 Phase 5: 通道适配器清理

**目标**: 移除通道适配器中的用户端功能

**修改文件**: `src/openakita/channels/adapters/*.py`

**删除内容**:
- sticker 相关的导入和调用
- persona 相关的导入和调用
- proactive 相关的导入和调用

**保留内容**:
- 基础消息收发
- 文件传输
- Webhook 处理
- 会话管理集成

### 3.6 Phase 6: 其他模块清理

**修改文件**:
1. `memory/types.py` - 移除 PERSONA_TRAIT 类型
2. `memory/daily_consolidator.py` - 移除用户端相关引用
3. `channels/types.py` - 移除 sticker 等消息类型支持（可选）

**删除目录**:
- `identity/personas/` - 人格预设目录
- `data/sticker/` - 表情包数据目录

---

## 4. Agent.py 详细修改方案

### 4.1 删除的导入语句

```python
# 第89-91行 删除:
from .user_profile import get_profile_manager

# 第290-293行 删除:
from ..config import runtime_state
from ..tools.sticker import StickerEngine
from .persona import PersonaManager
from .proactive import ProactiveConfig, ProactiveEngine
from .trait_miner import TraitMiner

# 第59-60行 删除:
from ..tools.handlers.persona import create_handler as create_persona_handler
from ..tools.handlers.sticker import create_handler as create_sticker_handler

# 第51行 删除:
from ..tools.handlers.profile import create_handler as create_profile_handler
```

### 4.2 删除的初始化代码

```python
# 第293行 删除:
runtime_state.load()

# 第296-303行 删除:
self.persona_manager = PersonaManager(
    personas_dir=settings.personas_path,
    active_preset=settings.persona_name,
)

# 第302-303行 删除:
self.trait_miner = TraitMiner(persona_manager=self.persona_manager, brain=self.brain)

# 第305-318行 删除:
proactive_config = ProactiveConfig(
    enabled=settings.proactive_enabled,
    max_daily_messages=settings.proactive_max_daily_messages,
    min_interval_minutes=settings.proactive_min_interval_minutes,
    quiet_hours_start=settings.proactive_quiet_hours_start,
    quiet_hours_end=settings.proactive_quiet_hours_end,
    idle_threshold_hours=settings.proactive_idle_threshold_hours,
)
self.proactive_engine = ProactiveEngine(
    config=proactive_config,
    feedback_file=settings.project_root / "data" / "proactive_feedback.json",
    persona_manager=self.persona_manager,
    memory_manager=self.memory_manager,
)

# 第320-323行 删除:
self.sticker_engine = StickerEngine(
    data_dir=settings.sticker_data_path,
) if settings.sticker_enabled else None
```

### 4.3 删除的 Handler 注册

```python
# 第903行 删除:
self.handler_registry.register("im_channel", create_im_channel_handler(self))

# 第932行 删除:
self.handler_registry.register("persona", create_persona_handler(self))

# 第939行 删除:
self.handler_registry.register("sticker", create_sticker_handler(self))

# 第946行 删除:
self.handler_registry.register("profile", create_profile_handler(self))
```

### 4.4 修改 PromptAssembler

```python
# 在 PromptAssembler.__init__ 中删除:
persona_manager: PersonaManager = None,

# 删除属性:
self.persona_manager = persona_manager

# 删除 _build_persona_section 方法
# 删除 _build_proactive_section 方法
```

### 4.5 删除的属性访问

确保删除以下属性的所有引用:
- `self.persona_manager`
- `self.trait_miner`
- `self.proactive_engine`
- `self.sticker_engine`
- `self.profile_manager`

---

## 5. 保留的核心架构

### 5.1 系统架构图（熵减后）

```
┌─────────────────────────────────────────────────────────────┐
│                        入口层                                │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│   Web UI    │  REST API   │ IM Channels │    CLI/Scheduler │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │               │
       └─────────────┴──────┬──────┴───────────────┘
                            │
                     ┌──────▼──────┐
                     │    Agent    │
                     └──────┬──────┘
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
┌──────▼──────┐      ┌──────▼──────┐      ┌──────▼──────┐
│    Brain    │      │   Memory    │      │   Context   │
│  (LLM调用)  │      │   System    │      │   Manager   │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
       ┌──────▼──────┐ ┌────▼────┐ ┌──────▼──────┐
       │   Legacy    │ │Enterprise│ │   Skills    │
       │   Backend   │ │  Backend │ │   System    │
       └─────────────┘ └──────────┘ └─────────────┘
```

### 5.2 工具系统（保留）

```
工具分类:
├── 核心工具 (保留)
│   ├── run_shell
│   ├── read_file
│   ├── write_file
│   ├── edit_file
│   ├── list_directory
│   ├── ask_user
│   ├── web_search
│   └── get_tool_info/get_skill_info
│
├── IM 通道工具 (保留核心)
│   ├── deliver_artifacts
│   ├── get_voice_file
│   ├── get_image_file
│   └── get_chat_history
│
├── 记忆工具 (保留)
│   └── memory 相关工具
│
└── 已删除
    ├── persona 工具
    ├── sticker 工具
    └── profile 工具
```

### 5.3 通道支持（保留）

```
支持的通道:
├── seeagent-webui (主要)
├── REST API
├── Telegram (可选)
├── 飞书 (可选)
├── 企业微信 (可选)
├── 钉钉 (可选)
└── OneBot (可选)
```

---

## 6. 影响评估

### 6.1 对 webapp 的影响

| 功能 | 影响程度 | 说明 |
|------|----------|------|
| 聊天功能 | 无影响 | 核心功能独立 |
| 会话管理 | 无影响 | 使用 localStorage |
| 消息流式响应 | 无影响 | API 层独立 |
| 步骤展示 | 无影响 | 组件独立 |
| 附件展示 | 无影响 | Artifact 组件独立 |

### 6.2 对 API 的影响

| API 端点 | 影响程度 | 说明 |
|----------|----------|------|
| /chat | 无影响 | 核心对话 API |
| /sessions | 无影响 | 会话管理 |
| /config | 需修改 | 移除用户端配置 |
| /health | 无影响 | 健康检查 |

### 6.3 对通道适配器的影响

| 通道 | 影响程度 | 说明 |
|------|----------|------|
| Telegram | 轻微 | 移除 sticker 支持 |
| 飞书 | 轻微 | 移除 sticker 支持 |
| 企业微信 | 轻微 | 移除 sticker 支持 |
| 钉钉 | 轻微 | 移除 sticker 支持 |

---

## 7. 测试验证计划

### 7.1 单元测试

删除代码后需要确保通过:
- Memory 模块测试 (149 tests)
- Context 模块测试 (153 tests)
- Config 测试 (需更新)
- Agent 集成测试 (需更新)

### 7.2 集成测试

1. **Web UI 测试**
   - 新建会话
   - 发送消息
   - 接收响应
   - 流式输出
   - 附件处理

2. **API 测试**
   - POST /chat
   - GET /sessions
   - GET /health

3. **通道测试**（可选）
   - 消息收发
   - 文件传输

### 7.3 回归测试

运行完整测试套件:
```bash
pytest tests/ -v --cov=src/openakita --cov-report=html
```

---

## 8. 执行顺序

### 8.1 推荐执行顺序

```
Phase 1: 配置清理 (5分钟)
    ↓
Phase 2: 工具定义清理 (10分钟)
    ↓
Phase 3: Handler 清理 (10分钟)
    ↓
Phase 4: 核心模块清理 (30分钟)
    ↓
Phase 5: 通道适配器清理 (15分钟)
    ↓
Phase 6: 其他模块清理 (10分钟)
    ↓
测试验证 (30分钟)
```

### 8.2 预计总时间

- **代码修改**: 约 2 小时
- **测试验证**: 约 30 分钟
- **总计**: 约 2.5 小时

---

## 9. 回滚计划

### 9.1 Git 分支策略

```bash
# 创建熵减分支
git checkout -b feature/entropy-reduction

# 每个阶段创建一个提交
git commit -m "refactor(phase1): clean up user-facing config"
git commit -m "refactor(phase2): remove user-facing tool definitions"
# ...

# 验证通过后合并
git checkout main
git merge feature/entropy-reduction
```

### 9.2 回滚方法

如果发现问题:
```bash
git revert <commit-hash>
# 或
git reset --hard main
```

---

## 10. 附录

### 10.1 删除文件清单

```
# 核心模块
src/openakita/core/persona.py
src/openakita/core/proactive.py
src/openakita/core/trait_miner.py
src/openakita/core/user_profile.py

# 工具
src/openakita/tools/sticker.py

# Handler
src/openakita/tools/handlers/persona.py
src/openakita/tools/handlers/sticker.py
src/openakita/tools/handlers/profile.py

# 工具定义
src/openakita/tools/definitions/persona.py
src/openakita/tools/definitions/sticker.py
src/openakita/tools/definitions/profile.py

# 数据目录
identity/personas/
data/sticker/
```

### 10.2 修改文件清单

```
src/openakita/config.py
src/openakita/core/agent.py
src/openakita/core/prompt_assembler.py
src/openakita/tools/definitions/__init__.py
src/openakita/tools/handlers/__init__.py
src/openakita/memory/types.py
src/openakita/channels/adapters/telegram.py
src/openakita/channels/adapters/feishu.py
src/openakita/channels/adapters/wework_bot.py
src/openakita/channels/adapters/dingtalk.py
```

### 10.3 测试文件更新

```
tests/core/test_agent.py (更新)
tests/test_config.py (更新)
tests/tools/test_handlers.py (更新)
```

---

## 11. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 遗漏依赖 | 中 | 高 | 全局搜索所有引用 |
| 测试失败 | 中 | 中 | 分阶段测试验证 |
| webapp 异常 | 低 | 高 | 独立测试 webapp |
| API 不兼容 | 低 | 中 | 保持 API 接口不变 |

---

*文档版本: 1.0*
*创建日期: 2026-02-23*
*作者: Enterprise Coder*
