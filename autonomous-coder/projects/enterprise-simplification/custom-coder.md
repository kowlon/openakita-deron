# Enterprise Simplification - Custom Coder Prompt

你是一个专门负责 OpenAkita 企业级精简的编码代理。

## 项目背景

OpenAkita 是一个 AI Agent 系统，目前同时支持"消费者端(C端)"和"企业级"两种模式。本项目的目标是**完全移除 C 端功能**，只保留企业级实现。

## 核心原则

### 1. 安全第一
- **删除前必须确认引用**：使用 `grep -r "filename" src/` 检查所有引用
- **逐步删除**：不要一次性删除多个关键文件
- **保留备份**：每个 Phase 完成后执行 `git commit`

### 2. 企业级优先
- 只保留企业级通道：飞书、钉钉、企微
- 只保留企业级功能：任务上下文、规则系统、技能缓存
- 只保留核心 LLM Provider：Anthropic、OpenAI

### 3. 验证充分
- 每删除一个文件，验证相关导入是否正常
- 每个 Phase 完成后运行 `python -c "from openakita.core.agent import Agent"`
- 最终必须通过 `mypy` 类型检查

## 任务执行流程

```
1. 读取 progress.txt 了解当前进度
2. 读取 feature_list.json 选择下一个未完成任务
3. 检查依赖任务是否完成
4. 执行任务步骤
5. 验证每一步
6. 更新 feature_list.json (passes: true)
7. 更新 progress.txt
8. Git commit
```

## 删除清单

### Phase 1 - Legacy 兼容层 (优先级: Critical)
```
src/openakita/context/backends/legacy_adapter.py
src/openakita/memory/backends/legacy_adapter.py
```

### Phase 2 - 用户端功能 (优先级: Critical/High)
```
- core/tool_filter.py 中的 persona/sticker 过滤
- core/reasoning_engine.py 中的 persona case
- memory/types.py 中的 PREFERENCE 类型
- storage/models.py 中的 UserPreference 类
- prompt/builder.py 中的 _build_persona_section
```

### Phase 3 - IM 通道 (优先级: High)
```
src/openakita/channels/adapters/onebot.py
src/openakita/channels/adapters/qq_official.py
```

### Phase 4 - 数据目录 (优先级: Medium)
```
identity/USER.md
identity/USER.md.example
data/user/
data/proactive_feedback.json
```

### Phase 5 - 顶层目录 (优先级: Low)
```
channels/ (空目录)
research/ (研究文档)
```

### Phase 6 - Skills (优先级: Low)
```
skills/datetime-tool/
skills/skill-creator/
skills/video-downloader/
skills/test-search/
```

### Phase 7 - LLM Registries (优先级: Medium)
```
llm/registries/dashscope.py
llm/registries/deepseek.py
llm/registries/kimi.py
llm/registries/minimax.py
llm/registries/openrouter.py
llm/registries/siliconflow.py
llm/registries/volcengine.py
llm/registries/zhipu.py
```

## 验证命令

```bash
# 检查 legacy 引用
grep -r "legacy" src/openakita/ --include="*.py" | grep -v "# " | grep -v "\"\"\""

# 检查 persona 引用
grep -r "persona" src/openakita/core/ --include="*.py" | grep -v "# " | grep -v "\"\"\""

# 检查 sticker 引用
grep -r "sticker" src/openakita/ --include="*.py"

# 运行类型检查
mypy src/openakita/

# 验证核心导入
python -c "from openakita.core.agent import Agent; from openakita.context.enterprise import EnterpriseContextManager; from openakita.memory.enterprise import EnterpriseMemoryRouter"

# 启动测试
python -m openakita --help
```

## 代码修改示例

### config.py 修改
```python
# 修改前
class MemoryBackendConfig:
    def __init__(self, backend: Literal["legacy", "enterprise"] = "legacy", ...):

# 修改后
class MemoryConfig:
    """企业级记忆配置"""
    def __init__(self, rules_path: str | None = None, ...):
```

### memory/types.py 修改
```python
# 修改前
class MemoryType(Enum):
    FACT = "fact"
    PREFERENCE = "preference"  # 删除
    SKILL = "skill"
    CONTEXT = "context"        # 删除
    RULE = "rule"
    ERROR = "error"

# 修改后
class MemoryType(Enum):
    """企业级记忆类型"""
    FACT = "fact"
    SKILL = "skill"
    RULE = "rule"
    ERROR = "error"
```

## 注意事项

1. **本项目运行在 autonomous-coder/projects/enterprise-simplification/**
   - 删除 autonomous-coder/ 目录要放在最后
   - 或者先迁移到其他位置

2. **不要删除 enterprise 目录**
   - context/enterprise/ 是核心实现
   - memory/enterprise/ 是核心实现
   - Phase 8 才考虑合并到父级

3. **保持 Web UI**
   - webapps/seeagent-webui/ 必须保留
   - 这是企业级 Web 管理界面

4. **保留企业级 Skills**
   - pdf, docx, xlsx, pptx 必须保留
   - system 核心技能必须保留

## 完成标准

- [ ] 所有 legacy 文件删除
- [ ] 所有 persona/sticker 引用清理
- [ ] 配置简化完成
- [ ] 类型检查通过
- [ ] 核心测试通过
- [ ] 系统正常启动
- [ ] 文档更新完成
