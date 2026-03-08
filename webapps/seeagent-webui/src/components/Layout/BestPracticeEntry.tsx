import type { BestPracticeTemplate } from '@/types/task'

// Mock templates for testing when API returns empty
const MOCK_TEMPLATES: BestPracticeTemplate[] = [
  {
    id: 'bp-code-review',
    name: '代码审查',
    description: '系统化的代码审查流程，包括静态分析、安全检查和性能评估',
    steps: [
      { name: '静态分析', description: '运行代码静态分析工具' },
      { name: '安全检查', description: '检查安全漏洞和风险' },
      { name: '性能评估', description: '分析性能瓶颈' },
    ],
  },
  {
    id: 'bp-api-design',
    name: 'API 设计',
    description: 'RESTful API 设计和文档生成标准流程',
    steps: [
      { name: '接口定义', description: '定义 API 接口规范' },
      { name: '数据建模', description: '设计数据模型和 Schema' },
      { name: '文档生成', description: '自动生成 API 文档' },
    ],
  },
  {
    id: 'bp-requirement',
    name: '需求分析',
    description: '从用户需求到技术方案的完整分析流程',
    steps: [
      { name: '需求收集', description: '收集和整理用户需求' },
      { name: '需求分析', description: '分析需求的可行性和优先级' },
    ],
  },
  {
    id: 'bp-testing',
    name: '自动化测试',
    description: '单元测试、集成测试和 E2E 测试的完整覆盖',
    steps: [
      { name: '单元测试', description: '编写和运行单元测试' },
      { name: '集成测试', description: '编写和运行集成测试' },
    ],
  },
]

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
  // Use mock templates if API returns empty (for testing phase)
  const displayTemplates = templates.length > 0 ? templates.slice(0, 4) : MOCK_TEMPLATES.slice(0, 4)

  return (
    <div className="mt-4 flex flex-col gap-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <p className="text-[#92a4c9] text-[9px] font-bold uppercase tracking-widest">
          Best Practices
        </p>
        <button
          onClick={onOpenAllPractices}
          className="text-[#92a4c9] text-[10px] cursor-pointer hover:text-white transition-colors font-medium"
          title="查看所有最佳实践"
        >
          更多
        </button>
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