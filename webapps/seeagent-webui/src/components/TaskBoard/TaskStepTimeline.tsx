import type { TaskStep } from '@/types/task'
import { TaskStepCard } from './TaskStepCard'

type TaskStepTimelineProps = {
  steps: TaskStep[]
  currentStepIndex: number
  onStepClick: (stepId: string) => void
}

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
    <div className="space-y-3">
      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
          <span>进度</span>
          <span>{currentStepIndex} / {steps.length}</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-2">
          <div
            className="bg-primary h-2 rounded-full transition-all duration-300"
            style={{ width: `${(currentStepIndex / steps.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Step cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {steps.map((step, index) => (
          <TaskStepCard
            key={step.id}
            step={step}
            isActive={index === currentStepIndex}
            onClick={() => onStepClick(step.id)}
          />
        ))}
      </div>
    </div>
  )
}

export default TaskStepTimeline