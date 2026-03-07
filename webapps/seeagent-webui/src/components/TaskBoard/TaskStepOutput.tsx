import { useState } from 'react'
import type { TaskStep } from '@/types/task'

type TaskStepOutputProps = {
  step: TaskStep | null
  onUpdate: (output: Record<string, unknown>) => void
  isEditing: boolean
}

export function TaskStepOutput({ step, onUpdate, isEditing }: TaskStepOutputProps) {
  const [editedOutput, setEditedOutput] = useState<string>(
    step ? JSON.stringify(step.output_result, null, 2) : ''
  )

  if (!step) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-500">
        <span className="material-symbols-outlined text-6xl mb-4">touch_app</span>
        <p>点击步骤卡片查看详情</p>
      </div>
    )
  }

  const handleSave = () => {
    try {
      const parsed = JSON.parse(editedOutput)
      onUpdate(parsed)
    } catch (e) {
      console.error('Invalid JSON:', e)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <div className={`
            w-3 h-3 rounded-full
            ${step.status === 'running' ? 'bg-primary animate-pulse' : ''}
            ${step.status === 'completed' ? 'bg-emerald-500' : ''}
            ${step.status === 'pending' ? 'bg-slate-600' : ''}
            ${step.status === 'failed' ? 'bg-red-500' : ''}
            ${step.status === 'skipped' ? 'bg-amber-500' : ''}
          `} />
          <h3 className="font-bold text-white">{step.name}</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">
            Step {step.index + 1}
          </span>
        </div>
      </div>

      {/* Description */}
      {step.description && (
        <div className="px-4 py-3 border-b border-slate-700 bg-slate-800/30">
          <p className="text-sm text-slate-300">{step.description}</p>
        </div>
      )}

      {/* Output content */}
      <div className="flex-1 overflow-auto p-4">
        {isEditing ? (
          <div className="h-full flex flex-col">
            <textarea
              value={editedOutput}
              onChange={(e) => setEditedOutput(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-4 font-mono text-sm text-slate-300 resize-none focus:outline-none focus:border-primary"
              placeholder="编辑输出 JSON..."
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => setEditedOutput(JSON.stringify(step.output_result, null, 2))}
                className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
              >
                重置
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-primary text-white text-sm rounded-lg hover:bg-primary/80 transition-colors"
              >
                保存
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Input args */}
            {Object.keys(step.input_args).length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-slate-400 mb-2">输入参数</h4>
                <pre className="bg-slate-900/50 rounded-lg p-3 text-xs text-slate-300 overflow-auto">
                  {JSON.stringify(step.input_args, null, 2)}
                </pre>
              </div>
            )}

            {/* Output result */}
            {Object.keys(step.output_result).length > 0 ? (
              <div>
                <h4 className="text-xs font-medium text-slate-400 mb-2">输出结果</h4>
                <pre className="bg-slate-900/50 rounded-lg p-3 text-xs text-slate-300 overflow-auto max-h-64">
                  {JSON.stringify(step.output_result, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="text-center text-slate-500 py-8">
                <span className="material-symbols-outlined text-4xl mb-2">output</span>
                <p>暂无输出</p>
              </div>
            )}

            {/* Artifacts */}
            {step.artifacts.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-slate-400 mb-2">制品</h4>
                <div className="flex flex-wrap gap-2">
                  {step.artifacts.map((artifact, index) => (
                    <div
                      key={index}
                      className="px-3 py-1.5 bg-slate-800 rounded-lg text-xs text-slate-300 flex items-center gap-2"
                    >
                      <span className="material-symbols-outlined text-sm">attachment</span>
                      {artifact}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* User feedback */}
            {step.user_feedback && (
              <div>
                <h4 className="text-xs font-medium text-slate-400 mb-2">用户反馈</h4>
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-sm text-amber-200">
                  {step.user_feedback}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Timestamps */}
      <div className="px-4 py-2 border-t border-slate-700 text-xs text-slate-500 flex justify-between">
        <span>创建: {new Date(step.created_at).toLocaleString()}</span>
        {step.finished_at && (
          <span>完成: {new Date(step.finished_at).toLocaleString()}</span>
        )}
      </div>
    </div>
  )
}

export default TaskStepOutput