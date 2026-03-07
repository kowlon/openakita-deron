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
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">{task.name}</h2>
            {task.description && (
              <p className="text-sm text-slate-400 mt-1">{task.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">
              ID: {task.id.slice(0, 8)}...
            </span>
          </div>
        </div>
      </div>

      {/* Status bar */}
      <TaskStatusBar
        status={task.status}
        onPause={onPause}
        onResume={onResume}
        onCancel={onCancel}
        onToggleEdit={() => setIsEditing(!isEditing)}
        isEditing={isEditing}
      />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Step timeline */}
        <div className="w-1/2 border-r border-slate-700 overflow-auto p-4">
          <TaskStepTimeline
            steps={task.steps}
            currentStepIndex={task.current_step_index}
            onStepClick={handleStepClick}
          />
        </div>

        {/* Right: Step output */}
        <div className="w-1/2 overflow-hidden">
          <TaskStepOutput
            step={selectedStep}
            onUpdate={handleUpdateOutput}
            isEditing={isEditing}
          />
        </div>
      </div>
    </div>
  )
}

export default TaskBoard