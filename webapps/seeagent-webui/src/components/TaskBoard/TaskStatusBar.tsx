import type { TaskStatusType } from '@/types/task'

type TaskStatusBarProps = {
  status: TaskStatusType
  onPause: () => void
  onResume: () => void
  onCancel: () => void
  onToggleEdit: () => void
  isEditing: boolean
}

export function TaskStatusBar({
  status,
  onPause,
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
    <div className="px-4 py-2 border-b border-slate-700 bg-slate-800/50">
      <div className="flex items-center justify-between">
        {/* Status indicator */}
        <div className="flex items-center gap-3">
          <div className={`
            ${config.color} w-2.5 h-2.5 rounded-full
            ${status === 'running' ? 'animate-pulse' : ''}
          `} />
          <span className="text-sm font-medium text-white flex items-center gap-1.5">
            <span className="material-symbols-outlined text-base">{config.icon}</span>
            {config.text}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {status === 'running' && (
            <button
              onClick={onPause}
              className="px-3 py-1.5 text-xs bg-amber-500/20 text-amber-400 rounded-lg hover:bg-amber-500/30 transition-colors flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-sm">pause</span>
              暂停
            </button>
          )}

          {status === 'paused' && (
            <button
              onClick={onResume}
              className="px-3 py-1.5 text-xs bg-primary/20 text-primary rounded-lg hover:bg-primary/30 transition-colors flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-sm">play_arrow</span>
              恢复
            </button>
          )}

          {(status === 'running' || status === 'paused' || status === 'pending') && (
            <button
              onClick={onCancel}
              className="px-3 py-1.5 text-xs bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-sm">cancel</span>
              取消
            </button>
          )}

          {status === 'completed' && (
            <button
              onClick={onToggleEdit}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors flex items-center gap-1 ${
                isEditing
                  ? 'bg-primary text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
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
    </div>
  )
}

export default TaskStatusBar