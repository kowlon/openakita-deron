/**
 * Task types for multi-task orchestration
 */

export type TaskStatus = 'pending' | 'running' | 'waiting_user' | 'completed' | 'cancelled' | 'failed'

export type StepStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'failed'

export interface TaskStep {
  step_id: string
  name: string
  description?: string
  status: StepStatus
  output?: Record<string, unknown>
  error?: string
  requires_confirmation: boolean
  started_at?: string
  completed_at?: string
}

export interface Task {
  task_id: string
  scenario_id: string
  scenario_name?: string
  status: TaskStatus
  total_steps: number
  completed_steps: number
  current_step?: TaskStep
  steps: TaskStep[]
  created_at: string
  updated_at?: string
  context?: Record<string, unknown>
  result?: Record<string, unknown>
}

export interface TaskState {
  task_id: string
  scenario_id: string
  session_id?: string
  status: TaskStatus
  initial_message?: string
  context: Record<string, unknown>
  total_steps: number
  completed_steps: number
  current_step_index: number
  created_at: string
  updated_at?: string
}

// API Response types
export interface TaskListResponse {
  tasks: Task[]
  total: number
}

export interface TaskCreateRequest {
  scenario_id: string
  session_id?: string
  context?: Record<string, unknown>
}

export interface TaskConfirmRequest {
  step_id: string
  edited_output?: Record<string, unknown>
}