import type { Session } from '@/types/session'
import { SessionList } from '@/components/Session/SessionList'

type LeftSidebarProps = {
  sessions: Session[]
  currentSessionId: string | null
  searchQuery: string
  onNewSession: () => void
  onSelectSession: (id: string) => void
  onDeleteSession: (id: string) => void
  onSearchChange: (query: string) => void
}

export function LeftSidebar({
  sessions,
  currentSessionId,
  searchQuery,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  onSearchChange,
}: LeftSidebarProps) {
  return (
    <aside className="w-72 bg-[#111722] border-r border-primary/10 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 flex flex-col gap-6">
        <div className="flex flex-col">
          <h1 className="text-white text-lg font-bold leading-normal tracking-tight flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">hub</span>
            SeeAgent
          </h1>
          <p className="text-[#92a4c9] text-xs font-medium uppercase tracking-widest">AI Orchestrator</p>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewSession}
          className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg h-11 bg-primary text-white text-sm font-bold leading-normal hover:bg-primary/90 transition-colors"
        >
          <span className="material-symbols-outlined text-[20px]">add</span>
          <span>New Chat</span>
        </button>

        {/* Search */}
        <div className="flex flex-col gap-1">
          <div className="relative flex items-center">
            <span className="material-symbols-outlined absolute left-3 text-[#92a4c9] text-[20px]">search</span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full h-10 bg-[#232f48] border-none rounded-lg pl-10 pr-4 text-white placeholder:text-[#92a4c9] text-sm focus:ring-1 focus:ring-primary focus:outline-none"
              placeholder="Search sessions..."
            />
          </div>
        </div>
      </div>

      {/* Session List */}
      <SessionList
        sessions={sessions}
        currentSessionId={currentSessionId}
        searchQuery={searchQuery}
        onSelectSession={onSelectSession}
        onDeleteSession={onDeleteSession}
      />

      {/* Bottom */}
      <div className="p-4 border-t border-[#232f48]">
        <div className="flex items-center gap-3 px-3 py-2 text-[#92a4c9] hover:text-white hover:bg-[#232f48] rounded-lg cursor-pointer transition-colors">
          <span className="material-symbols-outlined">settings</span>
          <span className="text-sm font-medium">Settings</span>
        </div>
      </div>
    </aside>
  )
}

export default LeftSidebar
