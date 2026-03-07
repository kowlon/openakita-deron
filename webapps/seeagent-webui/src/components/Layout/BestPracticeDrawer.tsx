import { useState, useEffect } from 'react'
import { BestPracticeList } from '@/components/TaskBoard/BestPracticeList'
import type { BestPracticeTemplate } from '@/types/task'

type BestPracticeDrawerProps = {
  isOpen: boolean
  onClose: () => void
  onCreateTask: (templateId: string) => void
}

// Static placeholder templates
const PLACEHOLDER_TEMPLATES: BestPracticeTemplate[] = [
  {
    id: 'template-1',
    name: '代码审查流程',
    description: '系统化的代码审查流程，包括静态分析、安全检查和性能评估',
    steps: [
      { name: '静态分析', description: '运行代码静态分析工具' },
      { name: '安全检查', description: '检查安全漏洞和风险' },
      { name: '性能评估', description: '分析性能瓶颈' },
      { name: '生成报告', description: '生成综合审查报告' },
    ],
  },
  {
    id: 'template-2',
    name: '需求分析工作流',
    description: '从用户需求到技术方案的完整分析流程',
    steps: [
      { name: '需求收集', description: '收集和整理用户需求' },
      { name: '需求分析', description: '分析需求的可行性和优先级' },
      { name: '技术方案', description: '制定技术实现方案' },
    ],
  },
  {
    id: 'template-3',
    name: 'API 设计流程',
    description: 'RESTful API 设计和文档生成标准流程',
    steps: [
      { name: '接口定义', description: '定义 API 接口规范' },
      { name: '数据建模', description: '设计数据模型和 Schema' },
      { name: '文档生成', description: '自动生成 API 文档' },
      { name: 'Mock 服务', description: '创建 Mock 服务用于测试' },
    ],
  },
  {
    id: 'template-4',
    name: '自动化测试流程',
    description: '单元测试、集成测试和 E2E 测试的完整覆盖',
    steps: [
      { name: '单元测试', description: '编写和运行单元测试' },
      { name: '集成测试', description: '编写和运行集成测试' },
      { name: '覆盖率分析', description: '分析测试覆盖率' },
    ],
  },
]

export function BestPracticeDrawer({
  isOpen,
  onClose,
  onCreateTask,
}: BestPracticeDrawerProps) {
  const [templates, setTemplates] = useState<BestPracticeTemplate[]>([])

  useEffect(() => {
    // TODO: Replace with API call when backend is ready
    setTemplates(PLACEHOLDER_TEMPLATES)
  }, [])

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <aside className="fixed right-0 top-0 h-full w-[480px] bg-[#111722] border-l border-primary/10 z-50 flex flex-col shadow-2xl animate-slide-in-right">
        {/* Header */}
        <header className="h-16 border-b border-primary/10 flex items-center justify-between px-5 bg-[#111722]/80 shrink-0">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[20px]">auto_awesome</span>
            最佳实践
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          <p className="text-slate-400 text-xs mb-4">
            选择一个最佳实践模板来快速启动任务。每个模板都包含预定义的执行步骤。
          </p>

          <BestPracticeList
            templates={templates}
            onCreateTask={(templateId) => {
              onCreateTask(templateId)
              onClose()
            }}
            maxVisible={10}
          />
        </div>
      </aside>
    </>
  )
}

export default BestPracticeDrawer