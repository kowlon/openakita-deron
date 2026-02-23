# OpenAkita Agent WebUI 需求文档

## 1. 整体布局

### 1.1 三栏布局
- **左侧栏（会话列表）**: 显示历史会话列表，支持搜索、新建、删除
- **中间栏（主内容区）**: 显示对话内容和执行过程
- **右侧栏（详情面板）**: 显示选中步骤的详细信息

### 1.2 响应式设计
- 支持桌面端和移动端适配

---

## 2. 中间栏 - 主内容区

### 2.1 欢迎页面
当没有会话时显示欢迎页面（ChatGPT 风格）：
- Logo 和标题
- 快捷操作卡片（网络搜索、文档处理、代码助手、数据分析）
- 输入框

### 2.2 对话区域

#### 2.2.1 消息显示
- **用户消息**: 右侧蓝色气泡
- **AI 消息**: 左侧带 AI 头像的气泡

#### 2.2.2 多轮对话（ChatGPT 风格）
- 新消息**追加**到对话列表末尾，不替换旧消息
- 每轮对话包含：用户问题 + AI 响应 + 执行过程

### 2.3 计时器显示

#### 2.3.1 TTFT（Time to First Token）
- **触发时机**: 用户发送消息后立即开始
- **计时起点**: 从 0 开始
- **停止时机**: 收到第一个 token 后立即停止
- **显示逻辑**:
  - 运行中：实时显示计时（如 "TTFT: 1.25s"）
  - 停止后：显示最终值，不再变化

#### 2.3.2 总计时
- **触发时机**: 与 TTFT 同时开始
- **计时起点**: 从 0 开始
- **停止时机**: 所有输出完成后
- **显示逻辑**:
  - 运行中：实时显示计时
  - 完成后：显示最终值

#### 2.3.3 计时器 UI
```
运行中状态:
[●] TTFT: 1.25s | 总计: 1.25s

完成状态:
TTFT: 0.85s | 总计: 3.52s
```

### 2.4 执行步骤显示

#### 2.4.1 步骤卡片规则
- **简单 Q&A**: 不显示步骤卡片，直接显示 AI 回答
- **复杂任务**: 显示核心步骤卡片

#### 2.4.2 核心步骤（显示）
| 步骤类型 | 显示标题 | 说明 |
|---------|---------|------|
| 网络搜索 | 网络搜索 | web_search, search |
| PDF 生成 | PDF 文件生成 | 生成 PDF 文件 |
| 文档生成 | 文档生成 | 生成 Word/Excel 等 |
| 意图分析 | 意图分析 | thinking 类型 |

#### 2.4.3 内部步骤（隐藏）
- Plan 管理（create_plan, update_plan 等）
- 文件读取（read_file）
- 命令执行（run_shell, bash）
- 技能信息获取（get_skill_info）
- 结果交付（deliver_artifacts）
- 总结/响应（总结, summary）

#### 2.4.4 步骤卡片样式
```
┌─────────────────────────────────────┐
│ 🔍 网络搜索                          │
│ ████████████░░░░░░░  running        │
│ 正在搜索: 马斯克 最新新闻            │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 📄 PDF 文件生成                ✅    │
│ 已生成: musk_profile.pdf (2.3MB)    │
└─────────────────────────────────────┘
```

### 2.5 AI 响应显示

#### 2.5.1 简单 Q&A
- 直接显示 AI 文本回复
- 不带"任务总结"标题

#### 2.5.2 复杂任务
- 显示"任务总结"标题
- 总结内容支持 Markdown 渲染

---

## 3. 文件卡片组件（新增需求）

### 3.1 触发条件
当 AI 生成文件（PDF、Word、Excel、图片等）时，显示文件卡片。

### 3.2 文件类型识别
从后端事件中识别：
- `write_file` 工具调用写入 .pdf/.docx/.xlsx/.png 等
- `deliver_artifacts` 事件中的文件列表

### 3.3 卡片样式
```
┌─────────────────────────────────────┐
│ 📄 musk_profile.pdf                 │
│ 文件大小: 2.3 MB                    │
│ ┌─────┐                             │
│ │ PDF │  [下载] [预览]              │
│ └─────┘                             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 📊 data_analysis.xlsx               │
│ 文件大小: 156 KB                    │
│ ┌─────┐                             │
│ │ XLS │  [下载]                     │
│ └─────┘                             │
└─────────────────────────────────────┘
```

### 3.4 文件卡片功能
- **图标**: 根据文件类型显示不同图标（PDF、Word、Excel、图片等）
- **文件名**: 显示完整文件名
- **文件大小**: 显示文件大小（KB/MB）
- **下载按钮**: 点击下载文件
- **预览按钮**: （可选）PDF 和图片支持预览

### 3.5 文件类型图标映射
| 文件类型 | 图标 | 颜色 |
|---------|-----|------|
| PDF | 📄 | 红色 |
| Word | 📝 | 蓝色 |
| Excel | 📊 | 绿色 |
| 图片 | 🖼️ | 紫色 |
| 其他 | 📁 | 灰色 |

---

## 4. 数据结构

### 4.1 会话（Session）
```typescript
interface Session {
  id: string
  title: string
  timestamp: number
  status: 'active' | 'completed' | 'paused'
  conversationHistory: ConversationTurn[]
}
```

### 4.2 对话轮次（ConversationTurn）
```typescript
interface ConversationTurn {
  id: string
  userMessage: string
  steps: Step[]           // 执行步骤
  summary: string | null  // AI 最终回复
  artifacts: Artifact[]   // 生成的文件（新增）
  timestamp: number
  // 计时信息
  startTime: number       // 消息发送时间
  firstTokenTime: number  // 首 token 时间
  endTime: number         // 完成时间
}
```

### 4.3 文件产物（Artifact）（新增）
```typescript
interface Artifact {
  id: string
  type: 'pdf' | 'word' | 'excel' | 'image' | 'other'
  filename: string
  filepath: string        // 服务器路径
  size?: number          // 文件大小（字节）
  downloadUrl?: string   // 下载链接
}
```

### 4.4 步骤（Step）
```typescript
interface Step {
  id: string
  type: 'llm' | 'tool' | 'skill' | 'thinking' | 'planning'
  status: 'pending' | 'running' | 'completed' | 'failed'
  title: string
  summary: string
  startTime: number
  endTime?: number
  duration?: number
  input?: Record<string, unknown>
  output?: string
  category: 'core' | 'internal'
}
```

---

## 5. 后端事件处理

### 5.1 SSE 事件类型
| 事件类型 | 用途 |
|---------|------|
| `thinking_start` | 思考开始（不显示步骤卡片） |
| `tool_call_start` | 工具调用开始 |
| `tool_call_end` | 工具调用结束 |
| `text_delta` | 文本输出（用于检测首 token） |
| `done` | 任务完成 |
| `artifact_created` | 文件生成（新增） |

### 5.2 TTFT 检测逻辑
```
1. 用户发送消息 → 记录 startTime
2. 收到 text_delta 事件 → 记录 firstTokenTime（仅第一次）
3. TTFT = firstTokenTime - startTime
4. TTFT 显示后不再变化
```

### 5.3 步骤过滤逻辑
```typescript
function shouldShowStep(step: Step): boolean {
  // 1. 如果是 internal 类别，隐藏
  if (step.category === 'internal') return false

  // 2. 检查是否匹配内部步骤模式
  if (INTERNAL_STEP_PATTERNS.some(p => p.test(step.title))) return false

  // 3. 检查是否匹配核心步骤模式
  if (CORE_STEP_PATTERNS.some(p => p.test(step.title))) return true

  // 4. 默认隐藏
  return false
}
```

---

## 6. 待修复的 Bug

### 6.1 TTFT 计时器问题
**问题描述**: TTFT 在首 token 输出后没有停止，后续步骤运行时继续增加

**修复方案**:
- TTFT 在收到 `text_delta` 首次事件后立即锁定值
- 后续步骤运行不影响 TTFT 显示

### 6.2 中间步骤不显示问题
**问题描述**: 复杂任务的执行步骤没有正确显示

**修复方案**:
- 检查 `useChat.ts` 中的步骤过滤逻辑
- 确保 `tool_call_start` 事件正确创建步骤
- 确保核心步骤的 `category` 正确设置为 `core`

---

## 7. 实现优先级

### P0 - 必须修复
1. TTFT 计时器在首 token 后停止
2. 中间步骤正确显示

### P1 - 高优先级
1. 文件卡片组件
2. 文件下载功能

### P2 - 中优先级
1. 文件预览功能
2. 步骤卡片动画效果

---

## 8. 文件结构

```
src/
├── components/
│   ├── Artifact/           # 新增：文件卡片组件
│   │   ├── ArtifactCard.tsx
│   │   └── index.ts
│   ├── Layout/
│   │   ├── MainContent.tsx   # 主内容区（需重构）
│   │   └── ...
│   ├── Step/
│   │   ├── StepTimeline.tsx  # 步骤时间线
│   │   └── ...
│   └── Timer/
│       └── ElapsedTimer.tsx  # 计时器（需修复）
├── hooks/
│   └── useChat.ts           # 聊天逻辑（需重构）
├── types/
│   ├── session.ts
│   ├── step.ts
│   └── artifact.ts          # 新增
└── App.tsx
```
