export type SessionStatus = 'active' | 'completed' | 'paused'

export interface Session {
  id: string
  title: string
  stepCount: number
  timestamp: number
  status: SessionStatus
  userMessage?: string
}

export interface SessionState {
  sessions: Session[]
  currentSessionId: string | null
  searchQuery: string
}
