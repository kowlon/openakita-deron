import { useState } from 'react'

/**
 * Best practice template for quick task creation
 */
interface QuickPractice {
  id: string
  name: string
  icon: string
}

/**
 * Default quick access best practices
 * These are commonly used templates shown in the sidebar
 */
const DEFAULT_QUICK_PRACTICES: QuickPractice[] = [
  { id: 'code-review-v1', name: 'Code Review', icon: 'code' },
  { id: 'extraction-v1', name: 'Extraction', icon: 'database' },
  { id: 'market-v1', name: 'Market', icon: 'trending_up' },
  { id: 'security-v1', name: 'Security', icon: 'security' },
]

type BestPracticeEntryProps = {
  onPracticeClick: (practiceId: string) => void
}

/**
 * BestPracticeEntry component
 * Displays a grid of quick access best practice templates in the sidebar
 */
export function BestPracticeEntry({ onPracticeClick }: BestPracticeEntryProps) {
  const [practices] = useState<QuickPractice[]>(DEFAULT_QUICK_PRACTICES)

  return (
    <div className="mt-4 flex flex-col gap-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <p className="text-[#92a4c9] text-[9px] font-bold uppercase tracking-widest">
          Best Practices
        </p>
        <span
          className="material-symbols-outlined text-[#92a4c9] text-[14px] cursor-pointer hover:text-white transition-colors"
          title="Click to start a best practice template for quick task creation"
        >
          info
        </span>
      </div>

      {/* Grid of practice buttons */}
      <div className="grid grid-cols-2 gap-1.5">
        {practices.map((practice) => (
          <button
            key={practice.id}
            onClick={() => onPracticeClick(practice.id)}
            className="px-2 py-1.5 bg-[#232f48]/50 border border-slate-700/50 text-slate-300 text-[9px] rounded-lg hover:bg-primary/20 hover:text-white hover:border-primary/50 transition-all text-left flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-[12px]">
              {practice.icon}
            </span>
            <span className="truncate">{practice.name}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default BestPracticeEntry