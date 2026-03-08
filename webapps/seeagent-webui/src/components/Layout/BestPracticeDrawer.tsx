import { useEffect } from 'react'
import { BestPracticeList } from '@/components/TaskBoard/BestPracticeList'
import type { BestPracticeTemplate } from '@/types/task'

type BestPracticeDrawerProps = {
  isOpen: boolean
  onClose: () => void
  onCreateTask: (templateId: string) => void
  templates: BestPracticeTemplate[]
}

export function BestPracticeDrawer({
  isOpen,
  onClose,
  onCreateTask,
  templates,
}: BestPracticeDrawerProps) {

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