/**
 * Scenario types for multi-task orchestration
 */

export type TriggerType = 'keyword' | 'regex' | 'intent'

export interface TriggerPattern {
  type: TriggerType
  keywords?: string[]
  pattern?: string
  priority: number
}

export interface ScenarioStep {
  step_id: string
  name: string
  description?: string
  output_key?: string
  skills?: string[]
  system_prompt?: string
  requires_confirmation: boolean
  dependencies?: string[]
}

export interface Scenario {
  scenario_id: string
  name: string
  description?: string
  category: string
  version: string
  trigger_patterns: TriggerPattern[]
  steps: ScenarioStep[]
  metadata?: {
    author?: string
    created_at?: string
    tags?: string[]
  }
}

// API Response types
export interface ScenarioListResponse {
  scenarios: Scenario[]
  total: number
}

export interface ScenarioMatchRequest {
  message: string
}

export interface ScenarioMatchResponse {
  matched: boolean
  scenario?: Scenario
  confidence?: number
}