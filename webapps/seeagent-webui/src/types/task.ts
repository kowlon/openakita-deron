/**
 * Task orchestration types for the web UI
 */

// Task status from the backend
export type TaskStatusType = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

// Step status from the backend
export type TaskStepStatusType = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

/**
 * SubAgent configuration
 */
export interface SubAgentConfig {
  name: string
  role: string
  system_prompt: string
  skills: string[]
  mcps: string[]
  tools: string[]
}

/**
 * Task step - a single execution unit within a task
 */
export interface TaskStep {
  id: string
  task_id: string
  index: number
  name: string
  description: string
  status: TaskStepStatusType
  sub_agent_config: SubAgentConfig
  input_args: Record<string, unknown>
  output_result: Record<string, unknown>
  artifacts: string[]
  user_feedback: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

/**
 * Orchestration task - represents a multi-step task
 */
export interface OrchestrationTask {
  id: string
  session_id: string
  template_id: string | null
  name: string
  description: string
  status: TaskStatusType
  current_step_index: number
  steps: TaskStep[]
  context_variables: Record<string, unknown>
  created_at: string
  updated_at: string
  completed_at: string | null
}

/**
 * Best practice template
 */
export interface BestPracticeTemplate {
  id: string
  name: string
  description: string
  steps: Array<{
    name: string
    description: string
  }>
}

/**
 * Task statistics
 */
export interface TaskStats {
  running: boolean
  templates_count: number
  sessions_cached: number
  template_ids: string[]
}

/**
 * Create task request
 */
export interface CreateTaskRequest {
  session_id: string
  template_id?: string
  name?: string
  description?: string
  input_payload?: Record<string, unknown>
}

/**
 * Update step request
 */
export interface UpdateStepRequest {
  output_result?: Record<string, unknown>
  user_feedback?: string
}