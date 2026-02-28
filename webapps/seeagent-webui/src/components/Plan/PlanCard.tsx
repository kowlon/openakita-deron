import { useState } from 'react'
import type { Plan, PlanStepStatus } from '@/types/plan'

type PlanCardProps = {
  plan: Plan
}

const STATUS_ICONS: Record<PlanStepStatus, string> = {
  pending: '⏳',
  in_progress: '▶️',
  completed: '✅',
  failed: '❌',
  skipped: '⏭️',
}

const STATUS_COLORS: Record<PlanStepStatus, string> = {
  pending: 'text-slate-500',
  in_progress: 'text-blue-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
  skipped: 'text-yellow-400',
}

export function PlanCard({ plan }: PlanCardProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  const completedSteps = plan.steps.filter(s => s.status === 'completed').length
  const totalSteps = plan.steps.length
  const progressPercent = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0

  const isCompleted = plan.status === 'completed'
  const isFailed = plan.status === 'failed'

  return (
    <div className="mb-6">
      <div className="rounded-xl bg-gradient-to-br from-slate-900 to-slate-800 border-2 border-primary/30 shadow-xl overflow-hidden animate-slide-in">
        {/* Header */}
        <div className="p-5 border-b border-primary/20">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">📋</span>
                <h3 className="text-lg font-bold text-white">任务计划</h3>
                {isCompleted && <span className="text-xl">🎉</span>}
                {isFailed && <span className="text-xl">⚠️</span>}
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">{plan.task_summary}</p>
            </div>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="ml-4 text-slate-400 hover:text-primary transition-colors"
            >
              <span className="material-symbols-outlined text-[24px]">
                {isExpanded ? 'expand_less' : 'expand_more'}
              </span>
            </button>
          </div>

          {/* Progress bar */}
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span>进度: {completedSteps}/{totalSteps} 完成</span>
              <span>{progressPercent.toFixed(0)}%</span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2.5 overflow-hidden">
              <div
                className={`h-2.5 rounded-full progress-bar-animated ${
                  isCompleted ? 'bg-emerald-500' : isFailed ? 'bg-red-500' : 'bg-primary'
                }`}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        </div>

        {/* Steps list */}
        {isExpanded && (
          <div className="p-5 space-y-3">
            {plan.steps.map((step, index) => (
              <div
                key={step.id}
                className={`p-4 rounded-lg border transition-all ${
                  step.status === 'in_progress'
                    ? 'bg-blue-500/10 border-blue-500/30 shadow-md animate-pulse-glow'
                    : step.status === 'completed'
                    ? 'bg-emerald-500/5 border-emerald-500/20'
                    : step.status === 'failed'
                    ? 'bg-red-500/10 border-red-500/30'
                    : 'bg-slate-800/50 border-slate-700/50'
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className={`text-xl flex-shrink-0 mt-0.5 ${
                    step.status === 'in_progress' ? 'animate-pulse' : ''
                  }`}>
                    {STATUS_ICONS[step.status]}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-sm font-semibold ${STATUS_COLORS[step.status]}`}>
                        步骤 {index + 1}/{totalSteps}
                      </span>
                      {step.duration && (
                        <span className="text-xs text-slate-500">
                          [{step.duration}s]
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-white mb-1">{step.description}</p>
                    {step.tool && (
                      <p className="text-xs text-slate-500">
                        工具: {step.tool}
                      </p>
                    )}
                    {step.result && (
                      <div className="mt-2 text-xs text-slate-400 bg-slate-900/50 rounded p-2">
                        {step.result}
                      </div>
                    )}
                    {step.status === 'in_progress' && (
                      <div className="mt-2 flex items-center gap-2 text-xs text-blue-400">
                        <span>执行中</span>
                        <div className="flex space-x-1">
                          <div className="w-1 h-1 rounded-full bg-blue-400 animate-bounce" />
                          <div className="w-1 h-1 rounded-full bg-blue-400 animate-bounce [animation-delay:-0.15s]" />
                          <div className="w-1 h-1 rounded-full bg-blue-400 animate-bounce [animation-delay:-0.3s]" />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        {isCompleted && (
          <div className="px-5 pb-5">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-center">
              <p className="text-sm font-semibold text-emerald-400">
                🎉 任务已完成！
              </p>
              {plan.summary && (
                <p className="text-xs text-slate-400 mt-1">{plan.summary}</p>
              )}
            </div>
          </div>
        )}

        {isFailed && (
          <div className="px-5 pb-5">
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-center">
              <p className="text-sm font-semibold text-red-400">
                ⚠️ 任务执行失败
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default PlanCard
