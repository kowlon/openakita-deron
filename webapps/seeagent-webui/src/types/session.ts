import type { Step } from './step'
import type { Artifact } from './artifact'
import type { Plan } from './plan'

export type SessionStatus = 'active' | 'completed' | 'paused'

// Conversation turn - represents one round of user-AI conversation
export interface ConversationTurn {
  id: string
  userMessage: string
  steps: Step[]
  summary: string | null
  timestamp: number
  // Timing information
  startTime?: number
  firstTokenTime?: number | null
  endTime?: number | null
  // Generated artifacts (files)
  artifacts?: Artifact[]
  // Plan information (for plan mode tasks)
  plan?: Plan | null
}

export interface Session {
  id: string
  title: string
  stepCount: number
  timestamp: number
  status: SessionStatus
  userMessage?: string
  conversationHistory?: ConversationTurn[]
}

export interface SessionState {
  sessions: Session[]
  currentSessionId: string | null
  searchQuery: string
}
