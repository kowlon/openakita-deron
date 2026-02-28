/**
 * Plan 相关类型定义
 */

export type PlanStatus = 'in_progress' | 'completed' | 'failed' | 'cancelled'

export type PlanStepStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped'

export interface PlanStep {
  id: string
  description: string
  tool?: string
  skills?: string[]
  status: PlanStepStatus
  result?: string
  started_at?: string
  completed_at?: string
  duration?: number
}

export interface Plan {
  id: string
  task_summary: string
  steps: PlanStep[]
  status: PlanStatus
  created_at: string
  completed_at?: string
  summary?: string
  logs?: string[]
}
