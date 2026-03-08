import type { TaskStep } from '@/types/task'

type TaskStepTimelineProps = {
  steps: TaskStep[]
  currentStepIndex: number
  onStepClick: (stepId: string) => void
}

/**
 * Get icon for step based on status
 */
function getStepIcon(status: string): string {
  if (status === 'completed') return 'check'
  if (status === 'running') return 'play_arrow'
  if (status === 'failed') return 'error'
  return 'circle' // Default icon for pending
}

/**
 * Horizontal step timeline component
 * Displays steps in a horizontal scrollable layout
 */
export function TaskStepTimeline({
  steps,
  currentStepIndex,
  onStepClick,
}: TaskStepTimelineProps) {
  if (steps.length === 0) {
    return (
      <div className="text-center text-slate-500 py-8">
        <span className="material-symbols-outlined text-4xl mb-2">hourglass_empty</span>
        <p>暂无步骤</p>
      </div>
    )
  }

  return (
    <div className="p-4 bg-slate-50 dark:bg-slate-800/30 overflow-x-auto no-scrollbar">
      <div className="flex gap-4 min-w-max">
        {steps.map((step, index) => {
          const isCompleted = step.status === 'completed'
          const isActive = index === currentStepIndex

          // Determine styles based on status
          const containerClass = isActive
            ? 'flex flex-col gap-2 w-32 relative'
            : `flex flex-col gap-2 w-32 ${isCompleted ? 'opacity-60' : 'opacity-40'}`

          const iconBgClass = isCompleted
            ? 'bg-emerald-500 text-white'
            : isActive
              ? 'bg-primary text-white ring-4 ring-primary/20'
              : 'bg-slate-300 dark:bg-slate-700 text-slate-500'

          const labelClass = isActive
            ? 'font-bold text-primary uppercase'
            : 'text-[10px] font-bold text-slate-500 uppercase'

          const nameClass = isActive
            ? 'text-xs font-bold text-slate-900 dark:text-white'
            : 'text-xs font-semibold dark:text-slate-300'

          return (
            <div
              key={step.id}
              onClick={() => onStepClick(step.id)}
              className={containerClass}
              style={{ cursor: 'pointer' }}
            >
              <div className="flex items-center gap-2">
                <span className={`h-6 w-6 rounded-full flex items-center justify-center ${iconBgClass}`}>
                  <span className="material-symbols-outlined text-sm">
                    {getStepIcon(step.status)}
                  </span>
                </span>
                <span className={labelClass}>Step {index + 1}</span>
              </div>
              <p className={nameClass}>{step.name}</p>
              {/* Active step indicator line */}
              {isActive && (
                <div className="absolute -bottom-4 left-0 right-0 h-1 bg-primary rounded-full" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default TaskStepTimeline