# OpenAkita 企业级精简方案 (v2)

> 创建日期: 2026-02-24
> 更新日期: 2026-02-24
> 状态: 待执行

---

## 一、项目概述

### 1.1 目标

将 OpenAkita 从"消费者端 + 企业级混合模式"精简为"纯企业级"架构，**保留所有企业级核心功能**。

### 1.2 保留原则（重要！）

| 类别 | 保留原因 | 具体内容 |
|------|----------|----------|
| **LLM Registries** | 企业可能需要多种 LLM | 所有 Provider 保留 |
| **调试输出** | 开发/排查必备 | tracing, logging, debug, llm_debug 等 |
| **Skills/MCP/Tools 机制** | 企业级核心能力 | 加载器、注册表、运行机制保留 |
| **Memory/Context 企业版** | 企业级核心模块 | enterprise 实现全部保留 |
| **Agent Loop** | 核心推理逻辑 | reasoning_engine, brain 等保留 |

### 1.3 精简范围

只删除**消费者端(C端)特有**的功能：
- 用户画像/偏好系统
- 活人感引擎
- 表情包/人格系统
- C端 IM 通道（QQ）
- Legacy 兼容层
- 具体 Skills 内容（机制保留）

---

## 二、删除清单（完整版）

### 2.1 必须删除的文件/目录

```
# === Legacy 兼容层 ===
src/openakita/context/backends/legacy_adapter.py
src/openakita/memory/backends/legacy_adapter.py

# === 用户端功能代码 ===
src/openakita/memory/extractor.py           # AI提取用户偏好
src/openakita/memory/daily_consolidator.py  # 每日用户记忆归纳
src/openakita/sessions/user.py              # 跨平台用户管理

# === C端 IM 通道 ===
src/openakita/channels/adapters/onebot.py
src/openakita/channels/adapters/qq_official.py

# === 用户数据文件 ===
identity/USER.md
identity/USER.md.example
data/user/
data/proactive_feedback.json

# === 顶层冗余目录 ===
channels/ (空目录)

# 注意：Skills 目录全部保留
```

### 2.2 需要修改的代码

```
# === 移除 PREFERENCE 类型 ===
src/openakita/memory/types.py
  - 删除 PREFERENCE = "preference"
  - 删除 CONTEXT = "context" (已被 TaskContext 替代)

# === 移除用户偏好模型 ===
src/openakita/storage/models.py
  - 删除 UserPreference 类

# === 清理 Persona/Sticker 工具过滤 ===
src/openakita/core/tool_filter.py
  - 从 CONSUMER_TOOLS 中移除 persona/sticker

# === 清理 Persona 处理逻辑 ===
src/openakita/core/reasoning_engine.py
  - 删除 persona 相关的 case 分支

# === 简化 Prompt 构建 ===
src/openakita/prompt/builder.py
  - 删除 _build_persona_section 函数
  - 删除 persona_manager 参数

# === 简化配置 ===
src/openakita/config.py
  - 移除 backend 选择逻辑 (legacy/enterprise)
  - 只保留 enterprise 配置
```

### 2.3 保留不变的模块

```
# === LLM 相关 - 全部保留 ===
src/openakita/llm/                          # 所有文件保留
src/openakita/llm/registries/               # 所有 Provider 保留

# === 调试相关 - 全部保留 ===
data/llm_debug/                             # LLM 调试日志
data/react_traces/                          # 推理追踪
data/retrospects/                           # 回顾数据
src/openakita/tracing/                      # 追踪模块（如存在）

# === 企业级核心 - 全部保留 ===
src/openakita/context/enterprise/           # 企业级上下文
src/openakita/memory/enterprise/            # 企业级记忆
src/openakita/core/agent.py                 # Agent 主逻辑
src/openakita/core/brain.py                 # LLM 调用
src/openakita/core/reasoning_engine.py      # 推理引擎（保留核心）

# === 工具/技能机制 - 全部保留 ===
src/openakita/tools/                        # 工具定义和处理器
src/openakita/skills/                       # 技能加载机制
src/openakita/mcp_servers/                  # MCP 服务器

# === 企业级 IM 通道 - 保留 ===
src/openakita/channels/adapters/feishu.py
src/openakita/channels/adapters/dingtalk.py
src/openakita/channels/adapters/wework_bot.py
```

---

## 三、删除总结

### 3.1 按类别统计

| 类别 | 删除项 | 保留项 |
|------|--------|--------|
| **Legacy 兼容层** | legacy_adapter.py (2个) | enterprise 实现 |
| **用户端功能** | extractor, consolidator, user.py | 企业级 memory/context |
| **IM 通道** | onebot, qq_official | feishu, dingtalk, wework |
| **数据类型** | PREFERENCE, CONTEXT, UserPreference | FACT, SKILL, RULE, ERROR |
| **Persona/Sticker** | 工具过滤、case处理 | 其他工具和推理逻辑 |
| **Skills 内容** | 6个非核心技能 | pdf, docx, xlsx, pptx, system |
| **数据文件** | USER.md, proactive_feedback | AGENT.md, MEMORY.md |

### 3.2 预期效果

| 指标 | 精简前 | 精简后 | 变化 |
|------|--------|--------|------|
| Python 文件 | ~244 | ~230 | -6% |
| Skills 目录 | 11 | 5 | -55% |
| 代码行数 | ~50k | ~45k | -10% |
| 配置复杂度 | 双模式 | 单模式 | 大幅降低 |
| 维护难度 | 高 | 中 | 降低 |

### 3.3 删除命令汇总

```bash
# === Phase 1: Legacy 兼容层 ===
rm src/openakita/context/backends/legacy_adapter.py
rm src/openakita/memory/backends/legacy_adapter.py

# === Phase 2: 用户端功能 ===
rm src/openakita/memory/extractor.py
rm src/openakita/memory/daily_consolidator.py
rm src/openakita/sessions/user.py

# === Phase 3: C端 IM 通道 ===
rm src/openakita/channels/adapters/onebot.py
rm src/openakita/channels/adapters/qq_official.py

# === Phase 4: 数据文件 ===
rm identity/USER.md identity/USER.md.example
rm -rf data/user/
rm data/proactive_feedback.json

# === Phase 5: 顶层目录 ===
rm -rf channels/  # 空目录

# 注意：Skills 目录全部保留，不删除任何技能
```

---

## 四、代码修改详情

### 4.1 memory/types.py

```python
# === 修改前 ===
class MemoryType(Enum):
    FACT = "fact"
    PREFERENCE = "preference"  # 删除
    SKILL = "skill"
    CONTEXT = "context"        # 删除（TaskContext 已替代）
    RULE = "rule"
    ERROR = "error"

# === 修改后 ===
class MemoryType(Enum):
    """企业级记忆类型"""
    FACT = "fact"      # 事实信息
    SKILL = "skill"    # 技能经验
    RULE = "rule"      # 规则约束
    ERROR = "error"    # 错误教训
```

### 4.2 storage/models.py

```python
# === 删除整个类 ===
# @dataclass
# class UserPreference:
#     key: str
#     value: Any
#     updated_at: datetime = field(default_factory=datetime.now)
```

### 4.3 config.py

```python
# === 修改前 ===
class MemoryBackendConfig:
    def __init__(self, backend: Literal["legacy", "enterprise"] = "legacy", ...):

# === 修改后 ===
class MemoryConfig:
    """企业级记忆配置（无需选择 backend）"""
    def __init__(
        self,
        rules_path: str | None = None,
        skills_path: str | None = None,
        max_step_summaries: int = 20,
        max_key_variables: int = 50,
    ):
        ...
```

### 4.4 core/tool_filter.py

```python
# === 删除这些工具过滤 ===
# "switch_persona", "get_persona_profile", "create_persona",
# "send_sticker", "get_sticker", "list_stickers",
```

### 4.5 prompt/builder.py

```python
# === 删除以下代码 ===
# def _build_persona_section(persona_manager): ...
# if persona_manager: ...
```

---

## 五、任务列表

| ID | 任务 | 优先级 | 状态 |
|----|------|--------|------|
| SIM-001 | 删除 context/backends/legacy_adapter.py | P0 | 待执行 |
| SIM-002 | 删除 memory/backends/legacy_adapter.py | P0 | 待执行 |
| SIM-003 | 删除 memory/extractor.py | P0 | 待执行 |
| SIM-004 | 删除 memory/daily_consolidator.py | P0 | 待执行 |
| SIM-005 | 删除 sessions/user.py | P0 | 待执行 |
| SIM-006 | 修改 memory/types.py 移除 PREFERENCE | P0 | 待执行 |
| SIM-007 | 修改 storage/models.py 删除 UserPreference | P0 | 待执行 |
| SIM-008 | 修改 config.py 移除 backend 选择 | P0 | 待执行 |
| SIM-009 | 清理 tool_filter.py persona/sticker | P1 | 待执行 |
| SIM-010 | 清理 reasoning_engine.py persona case | P1 | 待执行 |
| SIM-011 | 清理 prompt/builder.py persona section | P1 | 待执行 |
| SIM-012 | 删除 channels/adapters/onebot.py | P1 | 待执行 |
| SIM-013 | 删除 channels/adapters/qq_official.py | P1 | 待执行 |
| SIM-014 | 更新 channels/adapters/__init__.py | P1 | 待执行 |
| SIM-015 | 删除 identity/USER.md | P2 | 待执行 |
| SIM-016 | 删除 data/user/ 和 proactive_feedback.json | P2 | 待执行 |
| SIM-017 | 删除顶层空 channels/ 目录 | P2 | 待执行 |
| SIM-018 | 删除非核心 Skills 内容 | P2 | 待执行 |
| SIM-019 | 最终验证测试 | P0 | 待执行 |

**总计**: 19 个任务

---

## 六、验收标准

### 6.1 功能验收

- [ ] Legacy 适配器已删除
- [ ] 用户端功能代码已删除
- [ ] C端 IM 通道已删除
- [ ] PREFERENCE 类型已移除
- [ ] 配置简化完成

### 6.2 保留验证

- [ ] 所有 LLM Registries 正常工作
- [ ] 调试输出功能正常
- [ ] Skills/MCP/Tools 加载机制正常
- [ ] Memory/Context 企业版正常
- [ ] Agent Loop 正常运行
- [ ] 企业级 IM 通道正常

### 6.3 代码质量

- [ ] 无 legacy 引用
- [ ] 无 persona/sticker 引用（核心模块）
- [ ] mypy 类型检查通过
- [ ] 核心测试通过
- [ ] 系统正常启动

---

## 七、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 删除 legacy 后功能缺失 | 低 | Enterprise 实现已完整 |
| Import 路径错误 | 中 | 全局搜索验证 |
| 测试覆盖不足 | 低 | 保留核心测试 |

---

*文档版本: v2*
*更新时间: 2026-02-24*
