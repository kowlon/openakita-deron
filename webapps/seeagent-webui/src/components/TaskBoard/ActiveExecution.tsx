/**
 * Active Execution Component
 * Displays a list of active data sources being processed
 */

type Source = {
  id: string
  name: string
  status: 'active' | 'completed' | 'pending'
}

type ActiveExecutionProps = {
  sources: Source[]
}

export function ActiveExecution({ sources }: ActiveExecutionProps) {
  const activeCount = sources.filter(s => s.status === 'active').length

  if (sources.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold text-slate-500 dark:text-[#92a4c9] uppercase tracking-wider">
          Active Execution
        </h4>
        <span className="text-[10px] text-primary font-bold px-2 py-0.5 bg-primary/10 rounded">
          {activeCount} Source{activeCount !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="space-y-2">
        {sources.map((source) => (
          <div
            key={source.id}
            className="group border border-slate-200 dark:border-slate-800 rounded-lg bg-slate-50/50 dark:bg-slate-800/20 overflow-hidden transition-all"
          >
            <div className="flex items-center justify-between p-3 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800/40">
              <div className="flex items-center gap-3">
                {source.status === 'active' ? (
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                ) : (
                  <div className="w-2 h-2 rounded-full bg-slate-400" />
                )}
                <span className="text-sm font-medium dark:text-slate-200">{source.name}</span>
              </div>
              <span className="material-symbols-outlined text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-200 transition-transform">
                expand_more
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ActiveExecution