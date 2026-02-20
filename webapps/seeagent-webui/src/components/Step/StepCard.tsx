import type { Step, StepType } from '@/types/step'
import { StepStatusIcon } from './StepStatusIcon'
import { StepTypeIcon } from './StepTypeIcon'

type StepCardProps = {
  step: Step
  index: number
  isLast: boolean
  isExpanded: boolean
  onToggleExpand: () => void
  onClick: () => void
}

const TYPE_LABELS: Record<StepType, string> = {
  llm: 'LLM Processing',
  tool: 'Tool Execution',
  skill: 'Skill Execution',
  thinking: 'Thinking',
  planning: 'Planning',
}

export function StepCard({ step, index, isLast, isExpanded, onToggleExpand, onClick }: StepCardProps) {
  return (
    <div className="flex gap-4">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <StepStatusIcon status={step.status} />
        {!isLast && <div className="w-0.5 flex-1 bg-emerald-500/20 my-2" />}
      </div>

      {/* Card content */}
      <div className="flex-1 pb-4">
        <div
          onClick={onClick}
          className={`rounded-xl p-4 transition-all cursor-pointer group ${
            step.status === 'running'
              ? 'bg-background-dark border-2 border-primary shadow-lg'
              : 'bg-background-dark border border-primary/10 hover:border-primary/40 shadow-sm'
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${step.status === 'running' ? 'bg-primary/20' : 'bg-slate-800'}`}>
                <StepTypeIcon type={step.type} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white">
                  Step {index + 1}: {step.title}
                </h4>
                <p className="text-xs text-slate-400">
                  {TYPE_LABELS[step.type]} • {step.duration ? `${(step.duration / 1000).toFixed(1)}s` : '...'}
                </p>
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onToggleExpand()
              }}
              className="text-slate-500 hover:text-primary transition-colors"
            >
              <span className="material-symbols-outlined text-[20px]">
                {isExpanded ? 'expand_less' : 'expand_more'}
              </span>
            </button>
          </div>

          {/* Expanded summary */}
          {isExpanded && step.summary && (
            <div className="mt-4 p-3 bg-slate-900/50 rounded-lg text-xs leading-relaxed text-slate-300">
              <p className="font-medium text-primary mb-1">Execution Result:</p>
              {step.summary}
            </div>
          )}

          {/* Running progress */}
          {step.status === 'running' && step.progress && (
            <div className="mt-4 p-3 bg-slate-900/50 rounded-lg">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span>{step.progress.stage}</span>
                <span>{step.progress.message}</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-1.5">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all"
                  style={{ width: `${(step.progress.current / step.progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Running dots animation */}
          {step.status === 'running' && !step.progress && (
            <div className="mt-4 flex justify-end">
              <div className="flex space-x-1">
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" />
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]" />
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StepCard
