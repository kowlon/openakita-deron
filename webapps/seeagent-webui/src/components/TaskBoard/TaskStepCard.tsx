import { useState } from 'react'
import type { TaskStep } from '@/types/task'
import { TaskStepStatusIcon } from './TaskStepStatusIcon'

type TaskStepCardProps = {
  step: TaskStep
  isActive: boolean
  onClick: () => void
}

export function TaskStepCard({ step, isActive, onClick }: TaskStepCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const toggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsExpanded(!isExpanded)
  }

  return (
    <div
      onClick={onClick}
      className={`
        cursor-pointer rounded-xl p-4 transition-all group
        ${isActive
          ? 'bg-primary/10 border-2 border-primary shadow-lg shadow-primary/20'
          : 'bg-background-dark border border-primary/10 hover:border-primary/40 shadow-sm'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TaskStepStatusIcon status={step.status} size="sm" />
          <div>
            <h4 className="text-sm font-bold text-white">
              {step.name}
            </h4>
            <p className="text-xs text-slate-400">
              Step {step.index + 1}
            </p>
          </div>
        </div>

        {/* Status badge */}
        <div className={`
          px-2 py-1 rounded-full text-xs font-medium
          ${step.status === 'running' ? 'bg-primary/20 text-primary' : ''}
          ${step.status === 'completed' ? 'bg-emerald-500/20 text-emerald-500' : ''}
          ${step.status === 'pending' ? 'bg-slate-700 text-slate-400' : ''}
          ${step.status === 'failed' ? 'bg-red-500/20 text-red-500' : ''}
          ${step.status === 'skipped' ? 'bg-amber-500/20 text-amber-500' : ''}
        `}>
          {step.status}
        </div>
      </div>

      {/* Description */}
      {step.description && (
        <p className="mt-2 text-xs text-slate-400 line-clamp-2">
          {step.description}
        </p>
      )}

      {/* Expanded output */}
      {isExpanded && Object.keys(step.output_result).length > 0 && (
        <div className="mt-4 p-3 bg-slate-900/50 rounded-lg">
          <p className="font-medium text-primary mb-2 text-xs">Output:</p>
          <pre className="text-xs text-slate-300 overflow-auto max-h-40">
            {JSON.stringify(step.output_result, null, 2)}
          </pre>
        </div>
      )}

      {/* Expand button */}
      {Object.keys(step.output_result).length > 0 && (
        <button
          onClick={toggleExpand}
          className="mt-2 text-xs text-slate-500 hover:text-primary transition-colors flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-sm">
            {isExpanded ? 'expand_less' : 'expand_more'}
          </span>
          {isExpanded ? '收起' : '查看输出'}
        </button>
      )}
    </div>
  )
}

export default TaskStepCard