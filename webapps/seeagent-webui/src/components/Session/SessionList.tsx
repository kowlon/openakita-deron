import { useMemo } from 'react'
import type { Session } from '@/types/session'
import { SessionItem } from './SessionItem'

type SessionListProps = {
  sessions: Session[]
  currentSessionId: string | null
  searchQuery: string
  onSelectSession: (id: string) => void
  onDeleteSession: (id: string) => void
}

export function SessionList({
  sessions,
  currentSessionId,
  searchQuery,
  onSelectSession,
  onDeleteSession,
}: SessionListProps) {
  const filteredSessions = useMemo(() => {
    if (!searchQuery) return sessions
    const query = searchQuery.toLowerCase()
    return sessions.filter((s) => s.title.toLowerCase().includes(query))
  }, [sessions, searchQuery])

  if (filteredSessions.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-500 text-sm">
        {searchQuery ? 'No sessions found' : 'No sessions yet'}
      </div>
    )
  }

  return (
    <nav className="flex-1 overflow-y-auto px-2 space-y-1">
      {filteredSessions.map((session) => (
        <SessionItem
          key={session.id}
          session={session}
          isActive={session.id === currentSessionId}
          onSelect={() => onSelectSession(session.id)}
          onDelete={() => onDeleteSession(session.id)}
        />
      ))}
    </nav>
  )
}

export default SessionList
