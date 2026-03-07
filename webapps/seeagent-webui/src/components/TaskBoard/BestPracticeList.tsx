import { useState, useEffect } from 'react'
import type { BestPracticeTemplate } from '@/types/task'

type BestPracticeListProps = {
  templates: BestPracticeTemplate[]
  onCreateTask: (templateId: string) => void
  maxVisible?: number
}

export function BestPracticeList({
  templates,
  onCreateTask,
  maxVisible = 5,
}: BestPracticeListProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [filteredTemplates, setFilteredTemplates] = useState<BestPracticeTemplate[]>([])

  useEffect(() => {
    if (isExpanded) {
      setFilteredTemplates(templates)
    } else {
      setFilteredTemplates(templates.slice(0, maxVisible))
    }
  }, [templates, isExpanded, maxVisible])

  if (templates.length === 0) {
    return null
  }

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">auto_awesome</span>
          最佳实践
        </h3>
        {templates.length > maxVisible && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-primary hover:text-primary/80 transition-colors"
          >
            {isExpanded ? '收起' : `查看全部 (${templates.length})`}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {filteredTemplates.map((template) => (
          <button
            key={template.id}
            onClick={() => onCreateTask(template.id)}
            className="text-left p-3 bg-background-dark border border-primary/10 rounded-xl hover:border-primary/40 hover:bg-primary/5 transition-all group"
          >
            <div className="flex items-start gap-3">
              <div className="p-2 bg-primary/10 rounded-lg group-hover:bg-primary/20 transition-colors">
                <span className="material-symbols-outlined text-primary">rocket_launch</span>
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-bold text-white truncate">
                  {template.name}
                </h4>
                <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                  {template.description}
                </p>
                <div className="flex items-center gap-1 mt-2 text-xs text-slate-500">
                  <span className="material-symbols-outlined text-sm">layers</span>
                  {template.steps.length} 步骤
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

export default BestPracticeList