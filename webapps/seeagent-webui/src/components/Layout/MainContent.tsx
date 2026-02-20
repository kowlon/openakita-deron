import { useMemo } from 'react'
import type { Session, Step, ExecutionMode } from '@/types'
import { StepTimeline } from '@/components/Step/StepTimeline'

type MainContentProps = {
  session: Session | null
  steps: Step[]
  executionMode: ExecutionMode
  onModeChange: (mode: ExecutionMode) => void
  onStepClick: (stepId: string) => void
  onSendMessage: (message: string) => void
}

export function MainContent({
  session,
  steps,
  executionMode,
  onModeChange,
  onStepClick,
  onSendMessage,
}: MainContentProps) {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const message = formData.get('message') as string
    if (message?.trim()) {
      onSendMessage(message.trim())
      ;(e.target as HTMLFormElement).reset()
    }
  }

  // Extract summary from the last LLM Response step
  const summary = useMemo(() => {
    const responseStep = [...steps].reverse().find(
      (step) => step.type === 'llm' && step.status === 'completed' && step.output
    )
    return responseStep?.output || null
  }, [steps])

  // Check if all steps are completed
  const isCompleted = useMemo(() => {
    return steps.length > 0 && steps.every((step) => step.status === 'completed')
  }, [steps])

  return (
    <div className="h-full w-full bg-background-dark flex flex-col">
      {/* Header */}
      <header className="h-16 border-b border-primary/10 flex items-center justify-between px-6 bg-background-dark/50 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-primary">chat_bubble</span>
          <h2 className="font-semibold text-slate-200">{session?.title || 'New Chat'}</h2>
          {session && (
            <span className="bg-primary/20 text-primary text-[10px] font-bold uppercase px-2 py-0.5 rounded-full">
              {session.status === 'active' ? 'Active' : session.status}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Mode Switcher */}
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
            <button
              onClick={() => onModeChange('auto')}
              className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${
                executionMode === 'auto' ? 'bg-primary text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Auto
            </button>
            <button
              onClick={() => onModeChange('edit')}
              className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${
                executionMode === 'edit' ? 'bg-primary text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Edit
            </button>
          </div>
        </div>
      </header>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {session ? (
          <div className="space-y-8 max-w-2xl mx-auto">
            {/* User Message */}
            {session.userMessage && (
              <div className="flex justify-end items-start gap-3 ml-12">
                <div className="bg-primary text-white p-4 rounded-xl rounded-tr-none shadow-lg max-w-[80%]">
                  <p className="text-sm leading-relaxed">{session.userMessage}</p>
                </div>
                <div className="w-8 h-8 rounded-full bg-primary shrink-0 flex items-center justify-center">
                  <span className="text-white text-xs font-bold">U</span>
                </div>
              </div>
            )}

            {/* Steps */}
            <StepTimeline steps={steps} onStepClick={onStepClick} />

            {/* Summary Section */}
            {isCompleted && summary && (
              <div className="mt-6 p-4 bg-slate-800/50 border border-primary/20 rounded-xl">
                <div className="flex items-center gap-2 mb-3">
                  <span className="material-symbols-outlined text-primary text-xl">summarize</span>
                  <h3 className="text-sm font-semibold text-primary">任务总结</h3>
                </div>
                <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                  {summary}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <span className="material-symbols-outlined text-6xl text-slate-600 mb-4">chat</span>
              <p className="text-slate-500">Select or create a session to start</p>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-6 bg-background-dark/80 backdrop-blur-xl border-t border-primary/10 shrink-0">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex items-end gap-3 bg-[#1e293b] rounded-xl p-3 border border-slate-700 focus-within:border-primary transition-all">
            <button type="button" className="p-2 text-slate-400 hover:text-white transition-colors">
              <span className="material-symbols-outlined">attach_file</span>
            </button>
            <textarea
              name="message"
              className="flex-1 bg-transparent border-none text-white focus:ring-0 placeholder:text-slate-500 text-sm resize-none py-2 outline-none"
              placeholder="Type a message..."
              rows={2}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  ;(e.target as HTMLTextAreaElement).form?.requestSubmit()
                }
              }}
            />
            <button
              type="submit"
              className="bg-primary text-white rounded-lg p-2.5 flex items-center justify-center hover:bg-primary/90 transition-colors shadow-lg"
            >
              <span className="material-symbols-outlined">send</span>
            </button>
          </div>
          <div className="mt-2 flex items-center justify-between px-2">
            <div className="flex gap-4">
              <button type="button" className="text-[11px] text-slate-500 hover:text-slate-300 flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">bolt</span>
                GPT-4o Agent
              </button>
              <button type="button" className="text-[11px] text-slate-500 hover:text-slate-300 flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">public</span>
                Web Access
              </button>
            </div>
            <p className="text-[10px] text-slate-600">Enter to send, Shift+Enter for new line</p>
          </div>
        </form>
      </div>
    </div>
  )
}

export default MainContent
