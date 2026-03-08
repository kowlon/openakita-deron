/**
 * Preliminary Insights Component
 * Displays preliminary analysis results in a blue-bordered card
 */

type PreliminaryInsightsProps = {
  content: string
}

export function PreliminaryInsights({ content }: PreliminaryInsightsProps) {
  if (!content) {
    return null
  }

  return (
    <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
      <h4 className="text-xs font-bold text-slate-500 dark:text-[#92a4c9] uppercase tracking-wider">
        Preliminary Insights
      </h4>
      <div className="p-4 bg-blue-50/30 dark:bg-blue-900/10 border-l-2 border-primary/40 rounded-r-xl">
        <p className="text-sm text-slate-700 dark:text-slate-300 italic leading-relaxed whitespace-pre-wrap">
          {content}
        </p>
      </div>
    </div>
  )
}

export default PreliminaryInsights