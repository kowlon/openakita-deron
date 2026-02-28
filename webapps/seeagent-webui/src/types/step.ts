export type StepStatus = 'pending' | 'running' | 'completed' | 'failed'
export type StepType = 'llm' | 'tool' | 'skill' | 'thinking' | 'planning'
export type StepCategory = 'core' | 'internal'

export interface StepProgress {
  stage: string
  current: number
  total: number
  message: string
}

export interface Step {
  id: string
  type: StepType
  status: StepStatus
  title: string
  summary: string
  startTime: number
  endTime?: number
  duration?: number
  progress?: StepProgress
  input?: Record<string, unknown>
  output?: string
  outputData?: Record<string, unknown>
  error?: string
  category?: StepCategory
}

export type ExecutionMode = 'auto' | 'edit'

/**
 * Core step keywords - these represent meaningful business operations
 * Only show: 意图识别(thinking), 网络搜索(search), PDF/文件生成(pdf/write)
 */
export const CORE_STEP_PATTERNS = [
  // Search and query - 核心业务操作
  /search/i,
  /web\s*(browse|scrape|search)/i,

  // PDF and file generation - 核心输出操作
  /pdf/i,
  /write\s*(file|document)/i,
  /create\s*(file|document)/i,
  /生成/i,

  // Thinking/Intent analysis
  /意图/i,
  /分析/i,

  // Browser operations - 浏览器操作 (use browser_ prefix to avoid false positives)
  /browser_/i,
  /navigate/i,
  /screenshot/i,
]

/**
 * Internal step patterns - these should be hidden from the step list
 */
export const INTERNAL_STEP_PATTERNS = [
  // Plan management (internal)
  /^create_plan$/i,
  /^update_plan/i,
  /^complete_plan$/i,
  /^get_plan/i,
  /plan.*step/i,

  // Skill info retrieval (internal)
  /^get_skill_info$/i,
  /^get_skill/i,
  /^list_skill/i,

  // File operations (internal) - use [\s_]* to match both spaces and underscores in tool names
  /file[\s_]*read/i,
  /read[\s_]*file/i,
  /^read$/i,
  /write[\s_]*temp/i,
  /temp[\s_]*file/i,
  /\.tmp/i,
  /cache/i,

  // System operations - use [\s_]* for tool names with underscores
  /execute[\s_]*command/i,
  /run[\s_]*command/i,
  /shell/i,
  /bash/i,
  /terminal/i,

  // Config operations
  /config/i,
  /setting/i,
  /load[\s_]*config/i,

  // Internal checks
  /check[\s_]*status/i,
  /verify[\s_]*internal/i,
  /state[\s_]*check/i,

  // Delivery and summary - hide these cards
  /^deliver$/i,
  /交付/i,
  /deliver_artifacts/i,
  /^总结$/i,
  /^summar/i,
  /^response$/i,
]
