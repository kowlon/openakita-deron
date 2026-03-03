# SubAgent 编译器技术设计文档

> 版本: v1.0  
> 日期: 2026-03-03  
> 状态: 设计评审  
> 更新: 基于独立 Agent 架构的 SubAgent 编译与配置方案

---

## 1. 背景与目标

SubAgent 需要能够从一段“最佳实践文档描述”自动生成可复用的配置，并在运行期作为独立 Agent 实例加载执行。该配置允许人工后期调整，确保实践流程可持续维护与演进。

设计目标：

1. **与 WorkerAgent 一致的独立 Agent 架构**：SubAgent 不是 dataclass 配置对象，而是完整 Agent 实例。
2. **配置可生成、可调整、可回放**：编译产物以配置文件持久化，支持手工编辑后再加载。
3. **最小侵入集成**：复用现有 Skill、Tool、MCP 与 ReasoningEngine 体系。
4. **可验证可追溯**：编译过程可解释、产物可校验、运行时可回放。

---

## 2. 现有架构对齐与原则

### 2.1 WorkerAgent 架构参考

现有 WorkerAgent 在独立进程中创建完整 Agent 实例，并通过统一初始化流程加载身份、技能、MCP 与推理引擎。这表明 SubAgent 也应作为“真实 Agent”构建，仅通过配置区分能力与提示词。

对齐原则：

- **完整 Agent 实例化**：复用 `Agent.initialize()` 的核心初始化流程。
- **配置驱动**：通过 SubAgentConfig 限制工具与技能集合，注入独立系统提示词。
- **独立对话历史**：每个 SubAgent 拥有独立 messages。

### 2.2 SubAgent 与 WorkerAgent 的一致性

| 维度 | SubAgent | WorkerAgent |
|------|----------|-------------|
| 实例化 | 独立 Agent | 独立 Agent |
| 进程 | 同进程 | 独立进程 |
| 工具集 | 受限 | 可配置 |
| Prompt | 专用 | 可配置 |
| 生命周期 | 任务期间 | 长期运行 |
| 通信 | 直接调用 | ZMQ |

---

## 3. 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   SubAgent 编译与运行总览                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  最佳实践文档 ─┐                                                │
│               ├──► SubAgentCompiler ─► SubAgentConfig ─┐        │
│  Skills/Tools ┘                                     存储        │
│                                                                │
│  运行期: SubAgentFactory ─► SubAgent(Agent实例) ─► 执行任务      │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

核心模块：

- **SubAgentCompiler**：解析最佳实践文档并生成配置。
- **SubAgentConfig**：配置结构与校验规则。
- **SubAgentRegistry**：配置索引与版本管理。
- **SubAgentFactory**：基于配置创建 SubAgent 实例。

---

## 4. 编译器设计

### 4.1 输入与输出

**输入：**

1. 最佳实践文档（Markdown）
2. 系统技能与工具清单（Skills/Tools/MCP）
3. 编译选项（模式、约束、默认策略）

**输出：**

- SubAgentConfig 文件（YAML/JSON）

### 4.2 编译管线

```
文档读取
  └─► 结构化解析
        └─► 能力抽取
              └─► 提示词生成
                    └─► 工具匹配
                          └─► 校验与裁剪
                                └─► 配置输出
```

#### 4.2.1 文档读取与结构化解析

解析目标：

- 目标任务与场景说明
- 步骤定义（SubAgent 角色划分）
- 输出要求与约束条件

解析策略：

- 规则优先：标题、列表、表格提取结构
- 兜底策略：LLM 语义抽取结构化字段

#### 4.2.2 能力抽取与角色建模

对每个 SubAgent 角色提取：

- 名称、能力描述、职责边界
- 需要的工具与技能
- 输出格式与验收标准

#### 4.2.3 提示词生成

构建规则：

- 基础身份模板 + 角色能力描述
- 注入“输入/输出格式”与“质量约束”
- 注入“前置步骤输出”占位符

#### 4.2.4 工具匹配与裁剪

匹配策略：

1. 精确匹配：文档显式提到的工具/技能
2. 能力映射：通过能力到工具的映射表
3. 兜底过滤：缺失则回退到最小工具集

裁剪原则：

- 禁止未声明的危险工具
- 工具最小可用集优先

#### 4.2.5 校验与输出

校验项：

- 工具/技能是否存在于系统目录
- 提示词长度预算
- 输出格式完整性
- 配置版本与兼容性

---

## 5. SubAgent 配置结构

### 5.1 配置示例

```yaml
schema_version: "1.0"
subagent_id: "code-reviewer"
name: "CodeReviewer"
description: "专注代码审查与质量改进"
system_prompt: |
  你是代码审查专家，关注可读性、正确性与安全性。
  输出格式:
  - issues: [{severity, detail, suggestion}]
  - summary: string
tools:
  system_tools: ["read_file", "search_codebase"]
  skills: ["lint-helper", "security-audit"]
  mcp: []
capabilities:
  allow_shell: false
  allow_write: false
runtime:
  max_iterations: 12
  session_type: "cli"
  memory_policy: "task_scoped"
  prompt_budget: "standard"
metadata:
  source_doc: "best_practice_x.md"
  compiled_at: "2026-03-03T10:00:00Z"
  author: "subagent-compiler"
```

### 5.2 关键字段说明

| 字段 | 说明 |
|------|------|
| schema_version | 配置结构版本 |
| subagent_id | 唯一标识 |
| name/description | 角色名称与能力描述 |
| system_prompt | 角色系统提示词 |
| tools | 工具、技能、MCP 的可用集合 |
| capabilities | 高层能力限制开关 |
| runtime | 运行期参数 |
| metadata | 编译溯源信息 |

---

## 6. 运行期加载与实例化

### 6.1 SubAgentFactory

实例化流程：

1. 读取 SubAgentConfig
2. 创建 Agent 实例
3. 运行 `initialize()` 完成系统加载
4. 覆盖系统提示词与工具集合
5. 构建独立 Session 与 ReasoningEngine

### 6.2 系统提示词注入策略

- 主提示词以 `system_prompt` 为主
- 动态注入“前置步骤输出”
- 注入工具/技能清单以匹配能力边界

### 6.3 工具限制策略

实现方式：

- 在 Capability 执行层进行白名单过滤
- ToolCatalog 和 SkillCatalog 生成裁剪版清单
- MCP 工具仅允许配置中显式列出的 server/tool

---

## 7. 编译器输出目录结构

```
data/
  subagents/
    best_practice_x/
      manifest.json
      code-reviewer.yaml
      code-writer.yaml
      test-designer.yaml
```

说明：

- `manifest.json` 记录该最佳实践的 SubAgent 列表与版本关系
- 每个 SubAgent 对应一个可独立加载的配置文件

---

## 8. 校验与回退机制

### 8.1 编译期校验

- 工具与技能名称存在性
- Prompt 预算超限检测
- 输出格式规范校验
- 必填字段完整性

### 8.2 运行期校验

- 权限越界检查
- 工具调用白名单校验
- 任务超时与循环检测

### 8.3 回退策略

- 编译失败：回退到人工配置模板
- 工具不匹配：回退到最小工具集
- Prompt 超限：回退到精简模板

---

## 9. 与多任务编排的集成点

### 9.1 场景定义接入

最佳实践场景在 TaskScenario 中定义 SubAgent 列表，运行期从 SubAgentRegistry 加载对应配置。

### 9.2 Step 与 SubAgent 的映射

```
StepDefinition
  └─ subagent_id -> SubAgentConfig -> SubAgent实例
```

StepContext 中的产出通过模板注入到下一步 SubAgent 的系统提示词。

---

## 10. 设计风险与控制

| 风险 | 影响 | 控制措施 |
|------|------|----------|
| 文档结构不规范 | 编译失败 | 结构化模板 + LLM 兜底抽取 |
| 工具过度授权 | 安全风险 | 白名单裁剪 + 能力开关 |
| Prompt 过长 | 成本与失败 | 预算裁剪 + 精简模板 |
| 配置漂移 | 维护困难 | 版本化与 manifest 管理 |

---

## 11. 最小可行实现路径

1. SubAgentConfig schema + 读写
2. SubAgentCompiler 基础解析与输出
3. SubAgentFactory 运行期加载
4. 与 TaskSession 的最小集成

