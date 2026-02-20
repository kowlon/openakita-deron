import type { Session } from '@/types/session'

type SessionItemProps = {
  session: Session
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
}

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

export function SessionItem({ session, isActive, onSelect, onDelete }: SessionItemProps) {
  return (
    <div
      onClick={onSelect}
      className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors group ${
        isActive
          ? 'bg-primary/20 border border-primary/30'
          : 'hover:bg-[#232f48]'
      }`}
    >
      <div
        className={`flex items-center justify-center rounded-lg shrink-0 size-10 ${
          isActive ? 'bg-primary text-white' : 'bg-[#232f48] group-hover:bg-[#314161] text-white'
        }`}
      >
        <span className="material-symbols-outlined text-[20px]">chat</span>
      </div>
      <div className="flex flex-col min-w-0 flex-1">
        <p className={`text-sm font-semibold truncate ${isActive ? 'text-white' : 'text-slate-300'}`}>
          {session.title}
        </p>
        <p className="text-[#92a4c9] text-xs truncate">
          {session.stepCount} steps • {formatRelativeTime(session.timestamp)}
        </p>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
        className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all"
      >
        <span className="material-symbols-outlined text-[18px]">delete</span>
      </button>
    </div>
  )
}

export default SessionItem
