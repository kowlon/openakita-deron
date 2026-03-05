import { FC } from 'react'
import type { Task, TaskStatus } from '../../types/task'

interface TaskCardProps {
  task: Task
  onConfirm?: (stepId: string) => void
  onCancel?: () => void
  onSwitchStep?: (stepId: string) => void
  compact?: boolean
}

const statusColors: Record<TaskStatus, string> = {
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  waiting_user: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  cancelled: 'bg-gray-100 text-gray-500',
  failed: 'bg-red-100 text-red-700',
}

const statusLabels: Record<TaskStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  waiting_user: 'Waiting',
  completed: 'Completed',
  cancelled: 'Cancelled',
  failed: 'Failed',
}

export const TaskCard: FC<TaskCardProps> = ({
  task,
  onConfirm,
  onCancel,
  onSwitchStep,
  compact = false,
}) => {
  const progress = task.total_steps > 0
    ? Math.round((task.completed_steps / task.total_steps) * 100)
    : 0

  if (compact) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-3 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[task.status]}`}>
              {statusLabels[task.status]}
            </span>
            <span className="text-sm font-medium text-gray-900">
              {task.scenario_name || task.scenario_id}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">
              {task.completed_steps}/{task.total_steps}
            </span>
            <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[task.status]}`}>
              {statusLabels[task.status]}
            </span>
            <h3 className="text-sm font-semibold text-gray-900">
              {task.scenario_name || task.scenario_id}
            </h3>
          </div>
          <span className="text-xs text-gray-400 font-mono">
            {task.task_id.slice(0, 8)}
          </span>
        </div>
      </div>

      {/* Progress */}
      <div className="px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-500">Progress</span>
          <span className="text-xs text-gray-500">
            {task.completed_steps} / {task.total_steps} steps
          </span>
        </div>
        <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Current Step */}
      {task.current_step && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-100">
          <div className="text-xs text-gray-500 mb-1">Current Step</div>
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-gray-900">
                {task.current_step.name}
              </span>
              {task.current_step.description && (
                <p className="text-xs text-gray-500 mt-0.5">
                  {task.current_step.description}
                </p>
              )}
            </div>
            {task.current_step.requires_confirmation && task.status === 'waiting_user' && (
              <button
                onClick={() => onConfirm?.(task.current_step!.step_id)}
                className="px-3 py-1.5 bg-blue-500 text-white text-xs rounded-md hover:bg-blue-600 transition-colors"
              >
                Confirm
              </button>
            )}
          </div>
        </div>
      )}

      {/* Steps List */}
      {task.steps.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-100">
          <div className="text-xs text-gray-500 mb-2">Steps</div>
          <div className="space-y-1">
            {task.steps.map((step, index) => (
              <button
                key={step.step_id}
                onClick={() => onSwitchStep?.(step.step_id)}
                className={`w-full text-left px-2 py-1.5 rounded text-sm flex items-center gap-2 transition-colors ${
                  step.status === 'completed'
                    ? 'bg-green-50 text-green-700'
                    : step.status === 'running'
                    ? 'bg-blue-50 text-blue-700'
                    : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                }`}
              >
                <span className="w-5 h-5 rounded-full bg-white border flex items-center justify-center text-xs">
                  {index + 1}
                </span>
                <span className="flex-1">{step.name}</span>
                {step.status === 'completed' && (
                  <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-4 py-3 border-t border-gray-100 flex justify-end gap-2">
        {task.status === 'running' && onCancel && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-gray-600 text-sm rounded-md hover:bg-gray-100 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}