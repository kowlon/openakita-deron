import type { OrchestrationTask, TaskStatusType } from '@/types/task'

type TaskListProps = {
  tasks: OrchestrationTask[]
  currentTaskId: string | null
  onSelectTask: (taskId: string) => void
  onResumeTask: (taskId: string) => void
}

const statusColors: Record<TaskStatusType, string> = {
  pending: 'bg-slate-500',
  running: 'bg-primary animate-pulse',
  paused: 'bg-amber-500',
  completed: 'bg-emerald-500',
  failed: 'bg-red-500',
  cancelled: 'bg-slate-600',
}

export function TaskList({
  tasks,
  currentTaskId,
  onSelectTask,
  onResumeTask,
}: TaskListProps) {
  if (tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-slate-500">
        <span className="material-symbols-outlined text-4xl mb-2">history</span>
        <p className="text-sm">暂无历史任务</p>
      </div>
    )
  }

  // Group tasks by status
  const activeTasks = tasks.filter(t => t.status === 'running' || t.status === 'paused')
  const completedTasks = tasks.filter(t => t.status === 'completed')
  const otherTasks = tasks.filter(t => !['running', 'paused', 'completed'].includes(t.status))

  return (
    <div className="space-y-4">
      {/* Active tasks */}
      {activeTasks.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-slate-400 mb-2 px-1">进行中</h4>
          <div className="space-y-2">
            {activeTasks.map((task) => (
              <TaskListItem
                key={task.id}
                task={task}
                isActive={task.id === currentTaskId}
                onSelect={onSelectTask}
                onResume={onResumeTask}
              />
            ))}
          </div>
        </div>
      )}

      {/* Completed tasks */}
      {completedTasks.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-slate-400 mb-2 px-1">已完成</h4>
          <div className="space-y-2">
            {completedTasks.slice(0, 5).map((task) => (
              <TaskListItem
                key={task.id}
                task={task}
                isActive={task.id === currentTaskId}
                onSelect={onSelectTask}
                onResume={onResumeTask}
              />
            ))}
            {completedTasks.length > 5 && (
              <p className="text-xs text-slate-500 px-1">
                还有 {completedTasks.length - 5} 个任务...
              </p>
            )}
          </div>
        </div>
      )}

      {/* Other tasks */}
      {otherTasks.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-slate-400 mb-2 px-1">其他</h4>
          <div className="space-y-2">
            {otherTasks.map((task) => (
              <TaskListItem
                key={task.id}
                task={task}
                isActive={task.id === currentTaskId}
                onSelect={onSelectTask}
                onResume={onResumeTask}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

type TaskListItemProps = {
  task: OrchestrationTask
  isActive: boolean
  onSelect: (taskId: string) => void
  onResume: (taskId: string) => void
}

function TaskListItem({ task, isActive, onSelect, onResume }: TaskListItemProps) {
  return (
    <div
      onClick={() => onSelect(task.id)}
      className={`
        p-3 rounded-lg cursor-pointer transition-all
        ${isActive
          ? 'bg-primary/20 border border-primary/30'
          : 'bg-slate-800/50 border border-slate-700 hover:border-slate-600'
        }
      `}
    >
      <div className="flex items-center gap-3">
        {/* Status indicator */}
        <div className={`w-2 h-2 rounded-full ${statusColors[task.status]}`} />

        {/* Task info */}
        <div className="flex-1 min-w-0">
          <h5 className="text-sm font-medium text-white truncate">
            {task.name}
          </h5>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-slate-500">
              {task.steps.length} 步骤
            </span>
            {task.status === 'paused' && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onResume(task.id)
                }}
                className="text-xs text-primary hover:text-primary/80"
              >
                恢复
              </button>
            )}
          </div>
        </div>

        {/* Step progress */}
        <div className="text-xs text-slate-400">
          {task.current_step_index}/{task.steps.length}
        </div>
      </div>
    </div>
  )
}

export default TaskList