# SeeAgent WebUI 重构实施计划

本文档详细描述 SeeAgent WebUI 重构的具体实施步骤、代码修改方案和验证方法。

---

## 一、项目概述

### 1.1 目标
根据 `front_web_requirement.md` 需求文档，对现有 WebUI 进行重构，修复已知问题，实现缺失功能。

### 1.2 当前状态分析

| 模块 | 状态 | 问题 |
|------|------|------|
| 三栏布局 | ✅ 完成 | 无 |
| 会话管理 | ✅ 完成 | 无 |
| 步骤卡片 | ⚠️ 部分完成 | 过滤逻辑需优化 |
| 计时器 | ⚠️ 有Bug | TTFT 没有正确锁定 |
| Edit 模式 | ⚠️ 部分完成 | 缺少确认交互 |
| 文件卡片 | ❌ 未实现 | 需要 Artifact 组件 |
| 多轮对话 | ✅ 完成 | 无 |

### 1.3 优先级定义

- **P0**: 必须修复的 Bug，影响核心功能
- **P1**: 高优先级功能，影响用户体验
- **P2**: 中优先级功能，可选优化

---

## 二、REF-001: 修复 TTFT 计时器

### 2.1 问题描述
TTFT（Time to First Token）在首 token 输出后没有停止，后续步骤运行时继续增加。

### 2.2 预期行为
```
用户发送消息
    ↓
TTFT 开始计时（从 0 开始）
    ↓
收到第一个 text_delta 事件
    ↓
TTFT 立即锁定（例如 0.85s）
    ↓
后续步骤执行，TTFT 保持 0.85s 不变
    ↓
任务完成，TTFT 仍为 0.85s
```

### 2.3 代码修改方案

**文件**: `webapps/seeagent-webui/src/components/Timer/ElapsedTimer.tsx`

**当前代码问题**（第 100 行）：
```tsx
// 当前实现 - running 状态下使用 currentElapsed
TTFT: {ttft !== null ? formatTime(ttft) : formatTime(currentElapsed)}
```

**修改方案**：
```tsx
// 修改后 - ttft 一旦存在就显示锁定值
TTFT: {formatTime(ttft)}
```

同时需要确保 `ttft` 的计算只在 `firstTokenTime` 首次设置时计算一次。

### 2.4 验证步骤

1. 启动开发服务器：`cd webapps/seeagent-webui && pnpm dev`
2. 打开浏览器：http://localhost:5174
3. 发送消息："帮我查一下今天天气"
4. 观察 TTFT：
   - [ ] 发送后 TTFT 从 0 开始计时
   - [ ] 首个 token 到达后 TTFT 锁定为固定值（如 0.85s）
   - [ ] 后续步骤执行时 TTFT 不再变化
   - [ ] 总计时间持续计时直到完成

### 2.5 完成标准
- [x] 代码修改完成
- [ ] 浏览器手动验证通过
- [ ] 与需求文档描述一致

---

## 三、REF-002: 修复中间步骤不显示

### 3.1 问题描述
复杂任务的执行步骤没有正确显示。

### 3.2 预期行为

**场景**: 用户发送 `"帮我查查曾德龙是谁，并帮我写入到pdf文件里"`

**期望显示的步骤**：
```
步骤1: 🧠 意图分析
       识别到需要搜索"曾德龙"相关信息并输出为PDF

步骤2: 🔍 网络搜索
       正在搜索"曾德龙"相关信息...

步骤3: 📄 PDF输出
       正在生成PDF文件...

步骤4: ✅ 总结
       已完成搜索并输出PDF文件
```

**不应显示的内部步骤**：
- Plan 管理（create_plan, update_plan）
- 文件读取（read_file）
- 命令执行（run_shell）
- 配置加载

### 3.3 代码修改方案

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts`

**关键函数**: `categorizeStep`

**优化逻辑**：
```typescript
function categorizeStep(title: string, tool?: string, args?: Record<string, unknown>): StepCategory {
  const textToCheck = `${title} ${tool || ''}`.toLowerCase()

  // 1. 优先检查核心操作（PDF生成、搜索等）
  // ... 现有核心检查逻辑

  // 2. 检查内部模式（plan、config 等）
  // ... 现有内部检查逻辑

  // 3. 确保顺序正确：先检查核心，再检查内部
}
```

**修改点**：
1. 确保 `PDF文件生成`、`文档生成` 等标题正确识别为核心步骤
2. 确保 `execute_command`、`run_shell` 等正确识别为内部步骤（除非是 PDF 生成）
3. 添加调试日志帮助排查

### 3.4 验证步骤

1. 发送消息："帮我查查马斯克是谁"
2. 验证显示：
   - [ ] 显示网络搜索步骤卡片
   - [ ] 不显示 plan 管理步骤
   - [ ] 不显示配置加载步骤

3. 发送消息："帮我查查曾德龙是谁，写成pdf"
4. 验证显示：
   - [ ] 显示网络搜索步骤
   - [ ] 显示 PDF 文件生成步骤
   - [ ] 不显示中间的临时文件操作

### 3.5 完成标准
- [ ] 核心业务步骤正确显示
- [ ] 内部步骤正确隐藏
- [ ] 简单 Q&A 不显示步骤卡片

---

## 四、REF-003: 实现 Edit 模式完整交互

### 4.1 需求描述
Edit 模式下步骤完成后暂停，允许用户编辑结果，确认后才进入下一步。

### 4.2 交互流程

```
用户发送消息
    ↓
AI 开始执行步骤1（搜索）
    ↓
步骤1完成 → 进入编辑状态（暂停）
    ↓
用户编辑搜索结果（勾选/删除/添加）
    ↓
用户点击"确认，继续下一步"
    ↓
AI 使用编辑后的结果执行步骤2（生成PDF）
    ↓
步骤2完成 → 进入编辑状态（暂停）
    ↓
用户预览/编辑PDF内容
    ↓
用户点击"确认，继续下一步"
    ↓
任务完成
```

### 4.3 实现步骤

#### Step 1: 更新类型定义

**文件**: `webapps/seeagent-webui/src/types/step.ts`

```typescript
// 添加编辑状态类型
export type EditState = 'none' | 'editing' | 'confirmed' | 'skipped'

export interface EditableStep extends Step {
  editState?: EditState
  editableResults?: EditableResult[]
}

export interface EditableResult {
  id: string
  selected: boolean
  title: string
  content: string
  source?: string
}
```

#### Step 2: 创建 EditConfirmBar 组件

**文件**: `webapps/seeagent-webui/src/components/Step/EditConfirmBar.tsx`

```tsx
interface EditConfirmBarProps {
  onConfirm: () => void
  onSkip: () => void
  isConfirming: boolean
}

export function EditConfirmBar({ onConfirm, onSkip, isConfirming }: EditConfirmBarProps) {
  return (
    <div className="mt-4 p-4 bg-primary/10 border border-primary/30 rounded-xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-lg">edit</span>
          <span className="text-sm text-primary font-medium">编辑模式 - 等待用户确认</span>
        </div>
        <div className="flex gap-2">
          <button onClick={onSkip} className="px-4 py-2 text-slate-400 hover:text-white">
            跳过
          </button>
          <button
            onClick={onConfirm}
            disabled={isConfirming}
            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90"
          >
            {isConfirming ? '处理中...' : '确认，继续下一步 →'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

#### Step 3: 集成到 StepCard

**文件**: `webapps/seeagent-webui/src/components/Step/StepCard.tsx`

修改点：
- 添加 `executionMode` prop
- 步骤完成且 `executionMode === 'edit'` 时显示 `EditConfirmBar`

#### Step 4: 实现确认逻辑

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts`

添加方法：
```typescript
const confirmStep = useCallback((stepId: string, editedData?: unknown) => {
  // 发送确认请求到后端
  // 继续执行下一步
}, [])

const skipStep = useCallback((stepId: string) => {
  // 跳过当前步骤
  // 继续执行下一步
}, [])
```

### 4.4 验证步骤

1. 切换到 Edit 模式
2. 发送消息："帮我查查曾德龙是谁"
3. 验证：
   - [ ] 搜索步骤完成后显示"等待用户确认"
   - [ ] 显示"确认，继续下一步"按钮
   - [ ] 点击确认后继续执行
   - [ ] 点击跳过后跳过当前步骤

### 4.5 完成标准
- [ ] Edit 模式下步骤完成后暂停
- [ ] 显示确认/跳过按钮
- [ ] 确认后继续执行
- [ ] Auto 模式下自动继续

---

## 五、REF-004: 实现文件卡片组件

### 5.1 需求描述
当 AI 生成文件时，显示文件卡片，支持下载。

### 5.2 文件类型图标映射

| 文件类型 | 图标 | 颜色 |
|---------|-----|------|
| PDF | 📄 | 红色 |
| Word | 📝 | 蓝色 |
| Excel | 📊 | 绿色 |
| 图片 | 🖼️ | 紫色 |
| 其他 | 📁 | 灰色 |

### 5.3 实现步骤

#### Step 1: 创建类型定义

**文件**: `webapps/seeagent-webui/src/types/artifact.ts`

```typescript
export type ArtifactType = 'pdf' | 'word' | 'excel' | 'image' | 'other'

export interface Artifact {
  id: string
  type: ArtifactType
  filename: string
  filepath: string
  size?: number
  downloadUrl?: string
}

// 工具函数
export function getArtifactType(filename: string): ArtifactType {
  const ext = filename.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'pdf': return 'pdf'
    case 'doc':
    case 'docx': return 'word'
    case 'xls':
    case 'xlsx': return 'excel'
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'webp': return 'image'
    default: return 'other'
  }
}

export function getArtifactIcon(type: ArtifactType): string {
  const icons: Record<ArtifactType, string> = {
    pdf: 'picture_as_pdf',
    word: 'description',
    excel: 'table_chart',
    image: 'image',
    other: 'folder'
  }
  return icons[type]
}

export function getArtifactColor(type: ArtifactType): string {
  const colors: Record<ArtifactType, string> = {
    pdf: 'text-red-400',
    word: 'text-blue-400',
    excel: 'text-green-400',
    image: 'text-purple-400',
    other: 'text-slate-400'
  }
  return colors[type]
}

export function formatFileSize(bytes?: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
```

#### Step 2: 更新 Session 类型

**文件**: `webapps/seeagent-webui/src/types/session.ts`

```typescript
import type { Artifact } from './artifact'

export interface ConversationTurn {
  // ... 现有字段
  artifacts: Artifact[]  // 新增
}
```

#### Step 3: 创建 ArtifactCard 组件

**文件**: `webapps/seeagent-webui/src/components/Artifact/ArtifactCard.tsx`

```tsx
import type { Artifact } from '@/types/artifact'
import { getArtifactIcon, getArtifactColor, formatFileSize } from '@/types/artifact'

interface ArtifactCardProps {
  artifact: Artifact
  onDownload?: (artifact: Artifact) => void
}

export function ArtifactCard({ artifact, onDownload }: ArtifactCardProps) {
  const handleDownload = () => {
    if (artifact.downloadUrl) {
      window.open(artifact.downloadUrl, '_blank')
    } else if (artifact.filepath) {
      // 使用 filepath 构建下载链接
      window.open(`/api/files/download?path=${encodeURIComponent(artifact.filepath)}`, '_blank')
    }
    onDownload?.(artifact)
  }

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center gap-4">
        {/* 图标 */}
        <div className={`text-3xl ${getArtifactColor(artifact.type)}`}>
          <span className="material-symbols-outlined">{getArtifactIcon(artifact.type)}</span>
        </div>

        {/* 文件信息 */}
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-white truncate">{artifact.filename}</h4>
          {artifact.size && (
            <p className="text-xs text-slate-500">{formatFileSize(artifact.size)}</p>
          )}
        </div>

        {/* 下载按钮 */}
        <button
          onClick={handleDownload}
          className="px-3 py-1.5 bg-primary/20 text-primary rounded-lg hover:bg-primary/30 transition-colors"
        >
          <span className="material-symbols-outlined text-lg">download</span>
        </button>
      </div>
    </div>
  )
}
```

#### Step 4: 处理 artifact_created 事件

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts`

```typescript
// 在 handleSSEEvent 中添加
case 'artifact_created': {
  const artifact = eventRecord.artifact as Artifact
  setArtifacts((prev) => [...prev, artifact])
  break
}
```

#### Step 5: 集成到 MainContent

**文件**: `webapps/seeagent-webui/src/components/Layout/MainContent.tsx`

在步骤卡片后添加文件卡片列表：
```tsx
{/* 文件卡片 */}
{artifacts.length > 0 && (
  <div className="mt-4 space-y-3">
    {artifacts.map((artifact) => (
      <ArtifactCard key={artifact.id} artifact={artifact} />
    ))}
  </div>
)}
```

### 5.4 验证步骤

1. 发送消息："帮我查查马斯克，写成pdf文件"
2. 验证：
   - [ ] PDF 生成后显示文件卡片
   - [ ] 卡片显示 PDF 图标（红色）
   - [ ] 卡片显示文件名
   - [ ] 点击下载按钮可下载文件

### 5.5 完成标准
- [ ] Artifact 类型定义完整
- [ ] ArtifactCard 组件可用
- [ ] artifact_created 事件处理正确
- [ ] 文件下载功能正常

---

## 六、执行计划时间表

| 阶段 | 任务 | 预计时间 | 依赖 |
|------|------|---------|------|
| 阶段1 | REF-001: TTFT 修复 | 30 分钟 | 无 |
| 阶段2 | REF-002: 步骤显示修复 | 45 分钟 | 无 |
| 阶段3 | REF-003: Edit 模式实现 | 2 小时 | REF-002 |
| 阶段4 | REF-004: 文件卡片实现 | 1.5 小时 | 无 |
| 阶段5 | REF-005: 步骤交互优化 | 1 小时 | REF-001 |
| 阶段6 | REF-006: 文件预览（可选）| 1 小时 | REF-004 |
| 阶段7 | REF-007: 代码清理 | 30 分钟 | 全部 |

**总计**: 约 7 小时

---

## 七、验证检查清单

### 7.1 功能验证
- [ ] TTFT 计时器正确锁定
- [ ] 核心步骤正确显示
- [ ] 内部步骤正确隐藏
- [ ] Edit 模式确认交互正常
- [ ] 文件卡片正确显示
- [ ] 文件下载功能正常

### 7.2 构建验证
- [ ] `pnpm build` 无错误
- [ ] `pnpm lint` 无警告
- [ ] TypeScript strict 模式通过

### 7.3 浏览器验证
- [ ] Chrome 测试通过
- [ ] 响应式布局正常
- [ ] 无控制台错误

---

## 八、回滚方案

如果重构出现问题，可以通过以下方式回滚：

1. Git 回滚到重构前的 commit
2. 从 feature_list.json 的备份恢复
3. 逐个功能回滚，保留已完成的部分

---

*文档更新时间: 2026-02-21*
