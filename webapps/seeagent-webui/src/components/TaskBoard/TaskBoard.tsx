import { useState, useCallback } from 'react'
import type { OrchestrationTask } from '@/types/task'
import { TaskStepTimeline } from './TaskStepTimeline'
import { TaskStepOutput } from './TaskStepOutput'
import { TaskStatusBar } from './TaskStatusBar'

type TaskBoardProps = {
  task: OrchestrationTask | null
  onResume: () => void
  onPause: () => void
  onCancel: () => void
  onUpdateStep: (stepId: string, output: Record<string, unknown>) => void
}

export function TaskBoard({
  task,
  onResume,
  onPause,
  onCancel,
  onUpdateStep,
}: TaskBoardProps) {
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)

  const selectedStep = task?.steps.find(s => s.id === selectedStepId) || null

  const handleStepClick = useCallback((stepId: string) => {
    setSelectedStepId(stepId)
    setIsEditing(false)
  }, [])

  const handleUpdateOutput = useCallback((output: Record<string, unknown>) => {
    if (selectedStepId) {
      onUpdateStep(selectedStepId, output)
      setIsEditing(false)
    }
  }, [selectedStepId, onUpdateStep])

  if (!task) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500">
        <span className="material-symbols-outlined text-6xl mb-4">assignment</span>
        <p className="text-lg">暂无活跃任务</p>
        <p className="text-sm mt-2">选择最佳实践模板创建新任务</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Task header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">analytics</span>
          <h3 className="font-bold text-slate-900 dark:text-white">{task.name}</h3>
        </div>
        <button className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
          <span className="material-symbols-outlined">close</span>
        </button>
      </div>

      {/* Status bar with resume/cancel buttons */}
      <TaskStatusBar
        status={task.status}
        onPause={onPause}
        onResume={onResume}
        onCancel={onCancel}
        onToggleEdit={() => setIsEditing(!isEditing)}
        isEditing={isEditing}
      />

      {/* Horizontal Step List */}
      <TaskStepTimeline
        steps={task.steps}
        currentStepIndex={task.current_step_index}
        onStepClick={handleStepClick}
      />

      {/* Detail Output Section */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 no-scrollbar">
        <TaskStepOutput
          step={selectedStep}
          onUpdate={handleUpdateOutput}
          isEditing={isEditing}
        />
      </div>

      {/* Bottom Action Footer */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-background-dark shrink-0">
        <div className="flex items-center justify-between">
          <button className="flex items-center gap-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 text-xs font-bold">
            <span className="material-symbols-outlined text-lg">arrow_back</span>
            Previous Step
          </button>
          <button className="flex items-center gap-2 text-slate-400 cursor-not-allowed text-xs font-bold">
            Next Step
            <span className="material-symbols-outlined text-lg">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default TaskBoard