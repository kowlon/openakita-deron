import type { OrchestrationTask } from '@/types/task'

type TaskCardProps = {
  task: OrchestrationTask
  onOpenDetails: () => void
}

export function TaskCard({ task, onOpenDetails }: TaskCardProps) {
  const totalSteps = task.steps.length || 1
  const progress = (task.current_step_index / totalSteps) * 100

  // Status label configuration
  const statusConfig = {
    running: { bg: 'bg-primary/10', text: 'text-primary', label: 'RUNNING', icon: 'sync' },
    paused: { bg: 'bg-yellow-500/10', text: 'text-yellow-600 dark:text-yellow-400', label: 'PAUSED', icon: 'pause' },
    completed: { bg: 'bg-emerald-500/10', text: 'text-emerald-600 dark:text-emerald-400', label: 'COMPLETED', icon: 'check_circle' },
    failed: { bg: 'bg-red-500/10', text: 'text-red-600 dark:text-red-400', label: 'FAILED', icon: 'cancel' },
    cancelled: { bg: 'bg-slate-500/10', text: 'text-slate-500', label: 'CANCELLED', icon: 'block' },
    pending: { bg: 'bg-slate-500/10', text: 'text-slate-500', label: 'PENDING', icon: 'schedule' },
  }

  const status = statusConfig[task.status] || statusConfig.pending

  return (
    <div className="group relative bg-slate-100 dark:bg-slate-800 border border-primary/30 rounded-xl overflow-hidden shadow-xl ring-1 ring-primary/20 hover:ring-primary/50 transition-all cursor-pointer">
      {/* Left blue border */}
      <div className="absolute top-0 left-0 w-1 h-full bg-primary" />

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] font-bold text-primary uppercase tracking-widest mb-1">
              Active Best Practice
            </p>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">{task.name}</h3>
          </div>
          {/* Status Label */}
          <div className={`flex items-center gap-2 ${status.bg} ${status.text} px-2.5 py-1 rounded-full text-[11px] font-bold uppercase border border-current/20`}>
            <span className="material-symbols-outlined text-sm leading-none">{status.icon}</span>
            <span>{status.label}</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex items-center gap-4 mb-5">
          <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs font-bold text-slate-500">
            Step {task.current_step_index} of {task.steps.length}
          </span>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between">
          {/* Avatars */}
          <div className="flex -space-x-2">
            {task.steps.slice(0, 2).map((step, idx) => (
              <div
                key={step.id}
                className={`h-6 w-6 rounded-full border-2 border-slate-100 dark:border-slate-800 flex items-center justify-center ${
                  idx === 0 ? 'bg-slate-300 dark:bg-slate-600' : 'bg-primary/40'
                }`}
              >
                {idx === 1 && (
                  <span className="material-symbols-outlined text-[12px] text-white">search</span>
                )}
              </div>
            ))}
          </div>

          {/* Open Details button */}
          <button
            onClick={onOpenDetails}
            className="text-primary text-sm font-bold flex items-center gap-1 hover:gap-2 transition-all"
          >
            Open Details
            <span className="material-symbols-outlined text-lg">chevron_right</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default TaskCard