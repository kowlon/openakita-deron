import type { BestPracticeTemplate } from '@/types/task'

/**
 * Get icon based on template name/type
 */
function getTemplateIcon(name: string): string {
  const lowerName = name.toLowerCase()
  if (lowerName.includes('code') || lowerName.includes('代码')) return 'code'
  if (lowerName.includes('extract') || lowerName.includes('提取')) return 'database'
  if (lowerName.includes('market') || lowerName.includes('市场')) return 'trending_up'
  if (lowerName.includes('security') || lowerName.includes('安全')) return 'security'
  if (lowerName.includes('api')) return 'api'
  if (lowerName.includes('test') || lowerName.includes('测试')) return 'bug_report'
  if (lowerName.includes('review') || lowerName.includes('审查')) return 'rate_review'
  if (lowerName.includes('doc') || lowerName.includes('文档')) return 'description'
  return 'auto_awesome' // default icon
}

type BestPracticeEntryProps = {
  templates: BestPracticeTemplate[]
  onPracticeClick: (practiceId: string) => void
  onOpenAllPractices?: () => void
}

/**
 * BestPracticeEntry component
 * Displays a grid of quick access best practice templates in the sidebar
 */
export function BestPracticeEntry({ templates, onPracticeClick, onOpenAllPractices }: BestPracticeEntryProps) {
  // Limit to first 4 templates for the sidebar quick entry
  const displayTemplates = templates.slice(0, 4)

  return (
    <div className="mt-4 flex flex-col gap-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <p className="text-[#92a4c9] text-[9px] font-bold uppercase tracking-widest">
          Best Practices
        </p>
        <span
          onClick={onOpenAllPractices}
          className="material-symbols-outlined text-[#92a4c9] text-[14px] cursor-pointer hover:text-white transition-colors"
          title="查看所有最佳实践"
        >
          expand_more
        </span>
      </div>

      {/* Grid of practice buttons */}
      <div className="grid grid-cols-2 gap-1.5">
        {displayTemplates.map((template) => (
          <button
            key={template.id}
            onClick={() => onPracticeClick(template.id)}
            className="px-2 py-1.5 bg-[#232f48]/50 border border-slate-700/50 text-slate-300 text-[9px] rounded-lg hover:bg-primary/20 hover:text-white hover:border-primary/50 transition-all text-left flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-[12px]">
              {getTemplateIcon(template.name)}
            </span>
            <span className="truncate">{template.name}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default BestPracticeEntry