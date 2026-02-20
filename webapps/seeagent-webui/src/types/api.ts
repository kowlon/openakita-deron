// Chat API types
export interface ChatRequest {
  message: string
  conversation_id?: string
  endpoint?: string
  plan_mode?: boolean
  thinking_mode?: boolean
  thinking_depth?: string
  attachments?: Attachment[]
}

export interface Attachment {
  type: string
  url?: string
  path?: string
  name?: string
  size?: number
}

// SSE Event types
export type SSEEventType =
  | 'iteration_start'
  | 'thinking_start'
  | 'thinking_delta'
  | 'thinking_end'
  | 'text_delta'
  | 'tool_call_start'
  | 'tool_call_end'
  | 'plan_created'
  | 'plan_step_updated'
  | 'ask_user'
  | 'agent_switch'
  | 'error'
  | 'done'

export interface SSEEvent {
  type: SSEEventType
  [key: string]: unknown
}

export interface ToolCallStartEvent extends SSEEvent {
  type: 'tool_call_start'
  tool: string
  args?: Record<string, unknown>
  step_id?: string
}

export interface ToolCallEndEvent extends SSEEvent {
  type: 'tool_call_end'
  tool: string
  result?: string
  error?: string
  step_id?: string
}

export interface TextDeltaEvent extends SSEEvent {
  type: 'text_delta'
  content: string
}

export interface DoneEvent extends SSEEvent {
  type: 'done'
  usage?: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
    context_tokens?: number
    context_limit?: number
  }
}

export interface ErrorEvent extends SSEEvent {
  type: 'error'
  message: string
}
