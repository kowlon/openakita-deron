import type { Step, StepStatus, StepType } from '@/types'

type DetailPanelProps = {
  step: Step
  onClose: () => void
}

const STATUS_COLORS: Record<StepStatus, string> = {
  pending: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  running: 'bg-primary/10 text-primary border-primary/20',
  completed: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
  failed: 'bg-red-500/10 text-red-500 border-red-500/20',
}

const TYPE_COLORS: Record<StepType, string> = {
  llm: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  tool: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  skill: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  thinking: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  planning: 'bg-green-500/10 text-green-400 border-green-500/20',
}

const STATUS_LABELS: Record<StepStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Success',
  failed: 'Failed',
}

const TYPE_LABELS: Record<StepType, string> = {
  llm: 'LLM',
  tool: 'Tool',
  skill: 'Skill',
  thinking: 'Thinking',
  planning: 'Planning',
}

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function DetailPanel({
  step,
  onClose,
}: DetailPanelProps) {
  const handleCopyJson = (data: Record<string, unknown>) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2))
  }

  return (
    <aside className="w-96 bg-[#111722] border-l border-primary/10 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <header className="h-16 border-b border-primary/10 flex items-center justify-between px-5 bg-[#111722]/80 shrink-0">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[20px]">info</span>
          Step Details
        </h3>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
          <span className="material-symbols-outlined text-[20px]">close</span>
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        {/* Metadata */}
        <section className="p-5 border-b border-primary/10">
          <div className="flex flex-wrap gap-2 mb-4">
            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide border ${STATUS_COLORS[step.status]}`}>
              {STATUS_LABELS[step.status]}
            </span>
            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide border ${TYPE_COLORS[step.type]}`}>
              {TYPE_LABELS[step.type]}
            </span>
            <span className="px-2 py-1 rounded bg-slate-800 text-slate-400 text-[10px] font-bold uppercase tracking-wide">
              ID: {step.id.slice(0, 8)}
            </span>
          </div>

          {/* Step Title */}
          <div className="mb-4">
            <h4 className="text-white font-medium text-sm">{step.title}</h4>
            {step.summary && (
              <p className="text-slate-400 text-xs mt-1">{step.summary}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Start Time</p>
              <p className="text-xs text-white">{formatTime(step.startTime)}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">End Time</p>
              <p className="text-xs text-white">{step.endTime ? formatTime(step.endTime) : '-'}</p>
            </div>
            <div className="col-span-2">
              <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Duration</p>
              <p className="text-xs text-white font-mono">
                {step.duration ? `${step.duration.toLocaleString()}ms (${(step.duration / 1000).toFixed(1)}s)` : '-'}
              </p>
            </div>
          </div>
        </section>

        {/* Input */}
        {step.input && Object.keys(step.input).length > 0 && (
          <section className="p-5 border-b border-primary/10">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-bold text-slate-200 uppercase tracking-wider">Input Arguments</p>
              <button
                onClick={() => handleCopyJson(step.input!)}
                className="text-primary text-[10px] font-bold flex items-center gap-1 hover:underline"
              >
                <span className="material-symbols-outlined text-[14px]">content_copy</span>
                Copy JSON
              </button>
            </div>
            <div className="bg-black/40 rounded-lg p-3 font-mono text-[11px] text-primary/80 leading-relaxed overflow-x-auto">
              <pre>{JSON.stringify(step.input, null, 2)}</pre>
            </div>
          </section>
        )}

        {/* Output */}
        <section className="p-5">
          <p className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-4">Output Results</p>

          {step.output && (
            <div className="prose prose-invert prose-sm mb-4">
              <p className="text-xs text-slate-300 whitespace-pre-wrap">{step.output}</p>
            </div>
          )}

          {step.outputData && (
            <div className="bg-black/40 rounded-lg p-3 font-mono text-[11px] text-primary/80 leading-relaxed overflow-x-auto">
              <pre>{JSON.stringify(step.outputData, null, 2)}</pre>
            </div>
          )}

          {step.error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-400">
              <p className="font-bold mb-1">Error:</p>
              <p>{step.error}</p>
            </div>
          )}

          <button className="w-full mt-6 py-2 border border-slate-700 rounded text-[11px] font-bold text-slate-400 hover:text-white hover:border-slate-500 transition-all flex items-center justify-center gap-2">
            <span className="material-symbols-outlined text-[16px]">download</span>
            Download Full Output
          </button>
        </section>
      </div>
    </aside>
  )
}

export default DetailPanel
