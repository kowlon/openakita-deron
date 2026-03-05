import { useMemo, useState, useEffect, useRef } from 'react'
import type { Session, Step, ConversationTurn } from '@/types'
import type { Artifact } from '@/types/artifact'
import type { Plan } from '@/types/plan'
import type { Task } from '@/types/task'
import { StepTimeline } from '@/components/Step/StepTimeline'
import { ElapsedTimer } from '@/components/Timer/ElapsedTimer'
import { ArtifactList } from '@/components/Artifact/ArtifactList'
import { PlanCard } from '@/components/Plan/PlanCard'
import { TaskCard } from '@/components/Task/TaskCard'

type AskUserQuestion = {
  question?: string;
  questions?: Array<{
    id: string;
    prompt: string;
    options?: Array<{ id: string; label: string }>;
    allow_multiple?: boolean;
  }>;
  options?: Array<{ id: string; label: string }>;
} | null;

type MainContentProps = {
  session: Session | null
  conversationHistory: ConversationTurn[]
  steps: Step[]  // Current turn steps only
  allSteps?: Step[]  // All steps (for detail panel)
  onStepClick: (stepId: string) => void
  onSendMessage: (message: string, isAskUserAnswer?: boolean) => void
  isStreaming: boolean
  firstTokenTime: number | null
  messageSendTime: number | null
  llmOutput: string | null
  artifacts?: Artifact[]  // Current turn artifacts
  askUserQuestion?: AskUserQuestion
  activePlan?: Plan | null  // Active plan for Plan mode
  activeTask?: Task | null  // Active task for multi-task orchestration
  onTaskConfirm?: (stepId: string) => void
  onTaskCancel?: () => void
  onTaskSwitchStep?: (stepId: string) => void
}

/**
 * Format time in seconds (e.g., "3.25s")
 */
function formatTime(ms: number | null): string {
  if (!ms) return '0.00s'
  const seconds = ms / 1000
  return `${seconds.toFixed(2)}s`
}

/**
 * Individual conversation turn component
 */
function ConversationTurnItem({
  turn,
  onStepClick,
}: {
  turn: ConversationTurn
  onStepClick?: (stepId: string) => void
}) {
  // Filter to show only core steps
  const coreSteps = turn.steps.filter(s => s.category === 'core')

  return (
    <>
      {/* User Message */}
      <div className="flex justify-end items-start gap-3 ml-12">
        <div className="bg-primary text-white p-4 rounded-xl rounded-tr-none shadow-lg max-w-[80%]">
          <p className="text-sm leading-relaxed">{turn.userMessage}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-primary shrink-0 flex items-center justify-center">
          <span className="text-white text-xs font-bold">U</span>
        </div>
      </div>

      {/* AI Response with Avatar and Timer */}
      <div className="flex justify-start items-start gap-3 mr-12">
        {/* AI Avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary/60 shrink-0 flex items-center justify-center shadow-md">
          <span className="material-symbols-outlined text-white text-sm">smart_toy</span>
        </div>
        {/* Timer and Summary */}
        <div className="flex-1">
          {/* Timer */}
          <div className="text-xs text-slate-500 mb-2">
            {turn.startTime && (
              <span className="font-mono tabular-nums">
                TTFT: {formatTime(turn.firstTokenTime ? turn.firstTokenTime - turn.startTime : null)}
                {' | '}
                总计: {formatTime(turn.endTime ? turn.endTime - turn.startTime : null)}
              </span>
            )}
          </div>

          {/* Plan Card - show if this turn had a plan */}
          {turn.plan && (
            <div className="mb-3">
              <PlanCard plan={turn.plan} />
            </div>
          )}

          {/* Historical Steps (only for complex tasks with tool calls) */}
          {coreSteps.length > 0 && (
            <div className="mb-3">
              <StepTimeline
                steps={coreSteps}
                onStepClick={onStepClick || (() => {})}
              />
            </div>
          )}

          {/* Summary */}
          {turn.summary && (
            <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-xl">
              <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                {turn.summary}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

export function MainContent({
  session,
  conversationHistory,
  steps,
  onStepClick,
  onSendMessage,
  isStreaming,
  firstTokenTime,
  messageSendTime,
  llmOutput,
  artifacts = [],
  askUserQuestion,
  activePlan = null,
  activeTask = null,
  onTaskConfirm,
  onTaskCancel,
  onTaskSwitchStep,
}: MainContentProps) {
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [conversationHistory.length, steps.length, isStreaming, llmOutput])

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const message = formData.get('message') as string
    if (message?.trim()) {
      onSendMessage(message.trim())
      setInputValue('')
      ;(e.target as HTMLFormElement).reset()
    }
  }

  // Check if all steps are completed
  const isCompleted = useMemo(() => {
    // For simple Q&A (no steps), completed when we have llmOutput and not streaming
    // Also completed when we have askUserQuestion (waiting for user input)
    if (steps.length === 0) {
      return !isStreaming && (llmOutput !== null || askUserQuestion !== null)
    }
    // For tasks with steps, completed when all steps are done OR when askUserQuestion is set
    return !isStreaming && (steps.every((step) => step.status === 'completed') || askUserQuestion !== null)
  }, [steps, isStreaming, llmOutput, askUserQuestion])

  // Check if task is in progress (has steps but not all completed, or waiting for response)
  const isRunning = useMemo(() => {
    // For simple Q&A (no steps), running when streaming
    if (steps.length === 0) {
      return isStreaming
    }
    return !isCompleted && steps.some((step) => step.status === 'running' || step.status === 'pending')
  }, [steps, isCompleted, isStreaming])

  // Check if we're waiting for response (message sent but no output yet)
  const isWaiting = useMemo(() => {
    return isStreaming && steps.length === 0 && !llmOutput
  }, [isStreaming, steps.length, llmOutput])

  // Get current turn summary - prefer llmOutput for simple Q&A
  const currentSummary = useMemo(() => {
    // For simple Q&A, use llmOutput
    if (llmOutput) return llmOutput
    // For complex tasks, get from steps
    const responseStep = [...steps].reverse().find(
      (step) => step.type === 'llm' && step.status === 'completed' && step.output
    )
    return responseStep?.output || null
  }, [steps, llmOutput])

  // Check if we should show the welcome screen (no session and no steps)
  const showWelcome = !session && steps.length === 0

  // ========== Welcome Screen (ChatGPT Style) ==========
  if (showWelcome) {
    return (
      <div className="h-full w-full bg-background-dark flex flex-col items-center justify-center">
        <div className="w-full max-w-3xl px-6">
          {/* Logo and Title */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-primary/60 mb-6 shadow-lg shadow-primary/20">
              <span className="material-symbols-outlined text-white text-4xl">smart_toy</span>
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">OpenAkita Agent</h1>
            <p className="text-slate-400">智能助手，帮你完成复杂任务</p>
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 gap-3 mb-8">
            {[
              { icon: 'search', title: '网络搜索', desc: '搜索最新信息' },
              { icon: 'description', title: '文档处理', desc: '生成 PDF、Word 等' },
              { icon: 'code', title: '代码助手', desc: '编写、调试代码' },
              { icon: 'analytics', title: '数据分析', desc: '分析和可视化数据' },
            ].map((action) => (
              <button
                key={action.title}
                onClick={() => setInputValue(action.title)}
                className="flex items-start gap-3 p-4 bg-slate-800/50 border border-slate-700 rounded-xl text-left hover:bg-slate-800 hover:border-primary/30 transition-all group"
              >
                <span className="material-symbols-outlined text-primary text-xl mt-0.5 group-hover:scale-110 transition-transform">
                  {action.icon}
                </span>
                <div>
                  <div className="text-white font-medium text-sm">{action.title}</div>
                  <div className="text-slate-500 text-xs">{action.desc}</div>
                </div>
              </button>
            ))}
          </div>

          {/* Input Area */}
          <form onSubmit={handleSubmit} className="relative">
            <div className="flex items-end gap-3 bg-[#1e293b] rounded-2xl p-4 border border-slate-700 focus-within:border-primary transition-all shadow-xl">
              <textarea
                name="message"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                className="flex-1 bg-transparent border-none text-white focus:ring-0 placeholder:text-slate-500 text-base resize-none py-2 outline-none min-h-[56px] max-h-[200px]"
                placeholder="输入你的问题或任务..."
                rows={1}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (inputValue.trim()) {
                      (e.target as HTMLTextAreaElement).form?.requestSubmit()
                    }
                  }
                }}
              />
              <button
                type="submit"
                disabled={!inputValue.trim()}
                className="bg-primary text-white rounded-xl p-3 flex items-center justify-center hover:bg-primary/90 transition-colors shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="material-symbols-outlined">arrow_upward</span>
              </button>
            </div>
            <p className="text-center text-slate-600 text-xs mt-3">
              按 Enter 发送，Shift + Enter 换行
            </p>
          </form>
        </div>
      </div>
    )
  }

  // ========== Chat View ==========
  return (
    <div className="h-full w-full bg-background-dark flex flex-col">
      {/* Header */}
      <header className="h-14 border-b border-primary/10 flex items-center justify-between px-6 bg-background-dark/50 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-primary">chat_bubble</span>
          <h2 className="font-semibold text-slate-200">{session?.title || 'New Chat'}</h2>
        </div>
      </header>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="space-y-6 max-w-2xl mx-auto">
          {/* Historical Conversation Turns */}
          {conversationHistory.map((turn) => (
            <ConversationTurnItem
              key={turn.id}
              turn={turn}
              onStepClick={onStepClick}
            />
          ))}

          {/* Current Turn - User Message (only if not already in history) */}
          {session?.userMessage && !conversationHistory.some(t => t.userMessage === session.userMessage) && (
            <div className="flex justify-end items-start gap-3 ml-12">
              <div className="bg-primary text-white p-4 rounded-xl rounded-tr-none shadow-lg max-w-[80%]">
                <p className="text-sm leading-relaxed">{session.userMessage}</p>
              </div>
              <div className="w-8 h-8 rounded-full bg-primary shrink-0 flex items-center justify-center">
                <span className="text-white text-xs font-bold">U</span>
              </div>
            </div>
          )}

          {/* Current Turn - AI Response Area */}
          {/* Show if: user message exists AND not in history AND (has content OR waiting for response) */}
          {session?.userMessage && !conversationHistory.some(t => t.userMessage === session.userMessage) && (isWaiting || isRunning || isCompleted || steps.length > 0 || askUserQuestion || llmOutput || activePlan) && (
            <div className="flex justify-start items-start gap-3 mr-12">
              {/* AI Avatar */}
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary/60 shrink-0 flex items-center justify-center shadow-md">
                <span className="material-symbols-outlined text-white text-sm">smart_toy</span>
              </div>
              {/* Timer and Response */}
              <div className="flex-1">
                {/* Timer - starts counting from message send time */}
                <ElapsedTimer
                  startTime={messageSendTime}
                  firstTokenTime={firstTokenTime}
                  isRunning={isStreaming}
                  isCompleted={isCompleted}
                  endTime={isCompleted ? Date.now() : null}
                />

                {/* Plan Card - show if Plan mode is active */}
                {activePlan && (
                  <div className="mt-3">
                    <PlanCard plan={activePlan} />
                  </div>
                )}

                {/* Task Card - show if there's an active task */}
                {activeTask && (
                  <div className="mt-3">
                    <TaskCard
                      task={activeTask}
                      onConfirm={onTaskConfirm}
                      onCancel={onTaskCancel}
                      onSwitchStep={onTaskSwitchStep}
                    />
                  </div>
                )}

                {/* Current Steps (only for complex tasks with tool calls) */}
                {steps.length > 0 && (
                  <div className="mt-3">
                    <StepTimeline
                      steps={steps}
                      onStepClick={onStepClick}
                    />
                  </div>
                )}

                {/* AI Response - different display for simple Q&A vs complex task */}
                {isCompleted && currentSummary && (
                  steps.length > 0 ? (
                    /* Complex task - show with summary header */
                    <div className="mt-3 p-4 bg-slate-800/50 border border-primary/20 rounded-xl">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="material-symbols-outlined text-primary text-xl">summarize</span>
                        <h3 className="text-sm font-semibold text-primary">任务总结</h3>
                      </div>
                      <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                        {currentSummary}
                      </div>
                    </div>
                  ) : (
                    /* Simple Q&A - show response directly without header */
                    <div className="mt-3 text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                      {currentSummary}
                    </div>
                  )
                )}

                {/* Artifacts - show generated files */}
                {artifacts.length > 0 && (
                  <ArtifactList artifacts={artifacts} />
                )}

                {/* Ask User Question - shown when agent needs clarification */}
                {askUserQuestion && (
                  <div className="mt-4 p-4 bg-amber-900/20 border border-amber-500/30 rounded-xl">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="material-symbols-outlined text-amber-400 text-xl">help</span>
                      <span className="text-sm font-medium text-amber-400">需要确认</span>
                    </div>

                    {/* Simple question format */}
                    {askUserQuestion.question && (
                      <p className="text-sm text-slate-300 mb-3">{askUserQuestion.question}</p>
                    )}

                    {/* Multiple questions format */}
                    {askUserQuestion.questions && askUserQuestion.questions.length > 0 && (
                      <div className="space-y-4">
                        {askUserQuestion.questions.map((q, qIdx) => (
                          <div key={q.id || qIdx}>
                            <p className="text-sm text-slate-300 mb-2">{q.prompt}</p>
                            {q.options && q.options.length > 0 && (
                              <div className="space-y-2">
                                {q.options.map((option) => (
                                  <button
                                    key={option.id}
                                    onClick={() => {
                                      // Send the selected option as an ask_user answer
                                      console.log('[ask_user] User clicked option:', option.label, 'Calling onSendMessage with isAskUserAnswer=true')
                                      onSendMessage(option.label, true)
                                    }}
                                    className="w-full text-left px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm text-slate-300 hover:bg-slate-700 hover:border-primary/30 transition-all"
                                  >
                                    {option.label}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Simple options format (without questions array) */}
                    {!askUserQuestion.questions && askUserQuestion.options && askUserQuestion.options.length > 0 && (
                      <div className="space-y-2">
                        {askUserQuestion.options.map((option) => (
                          <button
                            key={option.id}
                            onClick={() => {
                              // Send the selected option as an ask_user answer
                              console.log('[ask_user-simple] User clicked option:', option.label, 'Calling onSendMessage with isAskUserAnswer=true')
                              onSendMessage(option.label, true)
                            }}
                            className="w-full text-left px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm text-slate-300 hover:bg-slate-700 hover:border-primary/30 transition-all"
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* No options - show text input hint */}
                    {!askUserQuestion.questions && !askUserQuestion.options && (
                      <div className="text-xs text-slate-500">
                        请在下方输入框中回答
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 bg-background-dark/80 backdrop-blur-xl border-t border-primary/10 shrink-0">
        <form onSubmit={handleSubmit} className="max-w-2xl mx-auto">
          <div className="flex items-end gap-3 bg-[#1e293b] rounded-xl p-3 border border-slate-700 focus-within:border-primary transition-all">
            <textarea
              name="message"
              className="flex-1 bg-transparent border-none text-white focus:ring-0 placeholder:text-slate-500 text-sm resize-none py-2 outline-none"
              placeholder="继续对话..."
              rows={1}
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
        </form>
      </div>
    </div>
  )
}

export default MainContent
