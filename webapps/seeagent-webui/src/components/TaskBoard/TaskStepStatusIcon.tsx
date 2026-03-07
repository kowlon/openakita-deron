import type { TaskStepStatusType } from '@/types/task'

type TaskStepStatusIconProps = {
  status: TaskStepStatusType
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'w-6 h-6 text-[14px]',
  md: 'w-8 h-8 text-[18px]',
  lg: 'w-10 h-10 text-[22px]',
}

export function TaskStepStatusIcon({ status, size = 'md' }: TaskStepStatusIconProps) {
  const sizeClass = sizeClasses[size]

  switch (status) {
    case 'pending':
      return (
        <div className={`${sizeClass} rounded-full bg-slate-700/50 text-slate-400 border border-slate-600 flex items-center justify-center`}>
          <span className="material-symbols-outlined">circle</span>
        </div>
      )
    case 'running':
      return (
        <div className={`${sizeClass} rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center animate-pulse`}>
          <span className="material-symbols-outlined animate-spin">sync</span>
        </div>
      )
    case 'completed':
      return (
        <div className={`${sizeClass} rounded-full bg-emerald-500/20 text-emerald-500 border border-emerald-500/30 flex items-center justify-center`}>
          <span className="material-symbols-outlined">check_circle</span>
        </div>
      )
    case 'failed':
      return (
        <div className={`${sizeClass} rounded-full bg-red-500/20 text-red-500 border border-red-500/30 flex items-center justify-center`}>
          <span className="material-symbols-outlined">cancel</span>
        </div>
      )
    case 'skipped':
      return (
        <div className={`${sizeClass} rounded-full bg-amber-500/20 text-amber-500 border border-amber-500/30 flex items-center justify-center`}>
          <span className="material-symbols-outlined">remove_circle</span>
        </div>
      )
  }
}

export default TaskStepStatusIcon