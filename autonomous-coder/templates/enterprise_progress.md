# 企业级 Memory & Context 重构实施计划模板

> 模板版本: 2.0
> 最后更新: 2026-02-23

---

## 一、项目概述

### 1.1 目标

将 OpenAkita 的 Memory 和 Context 模块从 C 端用户场景重构为企业级应用场景。

### 1.2 当前状态分析

| 模块 | 状态 | 问题 |
|------|------|------|
| Memory | ⚠️ 需重构 | 过度记录、向量依赖、无多租户支持 |
| Context | ⚠️ 需重构 | LLM 压缩开销大、被动触发、无限增长 |

### 1.3 优先级定义

- **P0**: 核心功能，必须完成
- **P1**: 重要功能，高优先级
- **P2**: 可选功能，中优先级

---

## 二、MEM-001: 定义 MemoryBackend 协议

### 2.1 目标

创建抽象协议接口，支持多种后端实现。

### 2.2 文件

- `src/openakita/memory/protocol.py`
- `tests/memory/test_protocol.py`

### 2.3 实现步骤

```python
# 步骤 1: 创建 Protocol 文件
# 步骤 2: 定义 MemoryBackend 类
# 步骤 3: 添加类型注解
# 步骤 4: 编写单元测试
```

### 2.4 验收标准

- [ ] MemoryBackend Protocol 定义完整
- [ ] mypy 类型检查通过
- [ ] 单元测试通过

---

## 三、MEM-002: 实现 SystemRuleStore

### 3.1 目标

实现系统规则存储，支持从 YAML/JSON 加载规则。

### 3.2 文件

- `src/openakita/memory/enterprise/rules.py`
- `tests/memory/enterprise/test_rules.py`

### 3.3 数据结构

```python
@dataclass
class SystemRule:
    id: str
    category: RuleCategory
    content: str
    priority: int
    enabled: bool
```

### 3.4 验收步骤

1. 启动测试：`pytest tests/memory/enterprise/test_rules.py -v`
2. 验证加载：创建 rules.yaml，验证加载正确
3. 验证过滤：禁用规则不返回

### 3.5 完成标准

- [ ] test_load_from_yaml 通过
- [ ] test_get_rules_by_category 通过
- [ ] test_disabled_rules_not_returned 通过
- [ ] test_rules_sorted_by_priority 通过

---

## 四、MEM-003: 实现 TaskContextStore

### 4.1 目标

实现任务级上下文存储，支持多租户隔离。

### 4.2 文件

- `src/openakita/memory/enterprise/task_context.py`
- `tests/memory/enterprise/test_task_context.py`

### 4.3 验收步骤

1. 启动测试：`pytest tests/memory/enterprise/test_task_context.py -v`
2. 验证隔离：不同租户数据不混淆
3. 验证限制：步骤摘要最多 20 条

### 4.4 完成标准

- [ ] test_start_task 通过
- [ ] test_end_task 通过
- [ ] test_record_step_completion 通过
- [ ] test_step_summaries_limit 通过
- [ ] test_tenant_isolation 通过
- [ ] test_to_prompt_format 通过

---

## 五、CTX-001: 定义 ContextBackend 协议

### 5.1 目标

创建抽象协议接口，支持多种上下文后端实现。

### 5.2 文件

- `src/openakita/context/protocol.py`
- `tests/context/test_protocol.py`

### 5.3 完成标准

- [ ] ContextBackend Protocol 定义完整
- [ ] mypy 类型检查通过

---

## 六、CTX-004: 实现 ConversationContext

### 6.1 目标

实现对话级上下文，**移除 LLM 压缩**，使用滑动窗口。

### 6.2 关键改进

```python
def _trim_if_needed(self):
    """滑动窗口裁剪 - 无 LLM 调用"""
    # 1. 按轮次限制
    rounds = self._count_rounds()
    if rounds <= self.MAX_ROUNDS:
        return

    # 2. 保留最近 N 轮
    keep_from = self._find_round_boundary(rounds - self.MAX_ROUNDS)
    self.messages = self.messages[keep_from:]
```

### 6.3 验收步骤

1. 添加 25 轮对话
2. 验证只保留 20 轮
3. 验证无 LLM 调用（延迟 < 10ms）

### 6.4 完成标准

- [ ] 滑动窗口正确工作
- [ ] 无 LLM 调用
- [ ] 延迟 < 10ms

---

## 七、E2E 测试规范

### 7.1 测试环境

```bash
# 1. 启动后端
cd src/openakita
python -m openakita.server --config config/enterprise-test.yaml

# 2. 启动前端
cd webapps/seeagent-webui
pnpm dev

# 3. 运行 E2E 测试
cd tests/e2e
npx playwright test
```

### 7.2 测试用例清单

#### Memory E2E
- [ ] MEM-E2E-001: 任务上下文创建和显示
- [ ] MEM-E2E-002: 步骤记录和摘要
- [ ] MEM-E2E-003: 系统规则注入
- [ ] MEM-E2E-004: 多租户隔离
- [ ] MEM-E2E-005: 任务结束清理

#### Context E2E
- [ ] CTX-E2E-001: 滑动窗口裁剪
- [ ] CTX-E2E-002: 上下文性能测试
- [ ] CTX-E2E-003: 三层上下文组装
- [ ] CTX-E2E-004: 工具调用配对保护

#### Full Flow E2E
- [ ] FULL-E2E-001: 复杂任务完整流程
- [ ] FULL-E2E-002: 错误恢复流程
- [ ] FULL-E2E-003: 性能基准测试

---

## 八、执行计划时间表

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

## 九、验收检查清单

### 9.1 功能验收

- [ ] Memory 系统三层存储正常工作
- [ ] Context 系统三层架构正常工作
- [ ] 滑动窗口裁剪正常（≤20 轮）
- [ ] 任务结束自动清理
- [ ] 多租户隔离正确
- [ ] 系统规则正确注入

### 9.2 性能验收

- [ ] 上下文构建延迟 < 50ms
- [ ] Memory 操作延迟 < 100ms
- [ ] 无 LLM 调用用于压缩
- [ ] 内存占用 < 50MB（无 embedding 模型）

### 9.3 测试验收

- [ ] 后端单元测试全部通过（38 个）
- [ ] Chrome 插件 E2E 测试全部通过（12 个）
- [ ] 测试覆盖率 > 80%

### 9.4 文档验收

- [ ] API 文档更新
- [ ] 配置文档更新
- [ ] 迁移指南完成

---

## 十、回滚方案

如果重构出现问题，可以通过以下方式回滚：

1. Git 回滚到重构前的 commit
2. 配置切换回 `backend: legacy`
3. 逐个功能回滚，保留已完成的部分

---

*文档更新时间: 2026-02-23*
