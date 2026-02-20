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

  // File operations (internal)
  /file\s*read/i,
  /read\s*file/i,
  /write\s*temp/i,
  /temp\s*file/i,
  /\.tmp/i,
  /cache/i,

  // System operations
  /execute\s*command/i,
  /run\s*command/i,
  /shell/i,
  /bash/i,
  /terminal/i,

  // Config operations
  /config/i,
  /setting/i,
  /load\s*config/i,

  // Internal checks
  /check\s*status/i,
  /verify\s*internal/i,
  /state\s*check/i,

  // Delivery and summary - hide these cards
  /^deliver$/i,
  /交付/i,
  /deliver_artifacts/i,
  /^总结$/i,
  /^summar/i,
  /^response$/i,
]
