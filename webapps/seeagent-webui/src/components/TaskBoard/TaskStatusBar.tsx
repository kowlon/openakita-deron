import type { TaskStatusType } from '@/types/task'

type TaskStatusBarProps = {
  status: TaskStatusType
  onPause?: () => void
  onResume: () => void
  onCancel: () => void
  onToggleEdit: () => void
  isEditing: boolean
}

export function TaskStatusBar({
  status,
  onResume,
  onCancel,
  onToggleEdit,
  isEditing,
}: TaskStatusBarProps) {
  const statusConfig = {
    pending: { color: 'bg-slate-500', text: '等待中', icon: 'schedule' },
    running: { color: 'bg-primary', text: '执行中', icon: 'sync' },
    paused: { color: 'bg-amber-500', text: '已暂停', icon: 'pause_circle' },
    completed: { color: 'bg-emerald-500', text: '已完成', icon: 'check_circle' },
    failed: { color: 'bg-red-500', text: '失败', icon: 'cancel' },
    cancelled: { color: 'bg-slate-600', text: '已取消', icon: 'block' },
  }

  const config = statusConfig[status]

  return (
    <>
      {/* Status indicator bar */}
      <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`
              ${config.color} w-2.5 h-2.5 rounded-full
              ${status === 'running' ? 'animate-pulse' : ''}
            `} />
            <span className="text-sm font-medium text-slate-700 dark:text-white flex items-center gap-1.5">
              <span className="material-symbols-outlined text-base">{config.icon}</span>
              {config.text}
            </span>
          </div>

          {status === 'completed' && (
            <button
              onClick={onToggleEdit}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors flex items-center gap-1 ${
                isEditing
                  ? 'bg-primary text-white'
                  : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-600'
              }`}
            >
              <span className="material-symbols-outlined text-sm">
                {isEditing ? 'done' : 'edit'}
              </span>
              {isEditing ? '完成编辑' : '编辑输出'}
            </button>
          )}
        </div>
      </div>

      {/* Resume/Cancel Banner */}
      {(status === 'paused' || status === 'running' || status === 'pending') && (
        <button
          onClick={status === 'paused' ? onResume : onCancel}
          className="w-full bg-yellow-500 hover:bg-yellow-600 text-slate-900 font-bold py-3 px-4 flex items-center justify-center gap-2 transition-colors"
        >
          <span className="material-symbols-outlined">play_circle</span>
          <span>{status === 'paused' ? 'Resume Task' : 'Cancel Task'}</span>
        </button>
      )}
    </>
  )
}

export default TaskStatusBar