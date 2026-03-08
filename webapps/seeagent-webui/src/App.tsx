import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { Agentation } from 'agentation'
import { ThreeColumnLayout } from './components/Layout/ThreeColumnLayout'
import { LeftSidebar } from './components/Layout/LeftSidebar'
import { MainContent } from './components/Layout/MainContent'
import { DetailPanel } from './components/Layout/DetailPanel'
import { BestPracticeDrawer } from './components/Layout/BestPracticeDrawer'
import { TaskBoard } from './components/TaskBoard/TaskBoard'
import { useChat } from './hooks/useChat'
import { useTasks, generateTemplateQuestions } from './hooks/useTasks'
import type { Session, Step, ConversationTurn } from './types'
import type { Plan } from './types/plan'
import type { BestPracticeTemplate } from './types/task'

// Extended Session type with conversation history
interface ExtendedSession extends Session {
  conversationHistory: ConversationTurn[]
}

// Storage key for sessions
const SESSIONS_STORAGE_KEY = 'openakita_sessions'

// Best practice templates (same as in BestPracticeDrawer)
const BEST_PRACTICE_TEMPLATES: BestPracticeTemplate[] = [
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

// Load sessions from localStorage
function loadSessions(): ExtendedSession[] {
  try {
    const saved = localStorage.getItem(SESSIONS_STORAGE_KEY)
    console.log('[loadSessions] Raw data from localStorage:', saved ? `${saved.length} chars` : 'null')
    if (saved) {
      const parsed = JSON.parse(saved)
      console.log('[loadSessions] Parsed sessions:', parsed.length, 'items')
      return parsed.map((s: ExtendedSession) => ({
        ...s,
        // Ensure timestamp is a number
        timestamp: typeof s.timestamp === 'number' ? s.timestamp : Date.now(),
      }))
    }
  } catch (e) {
    console.error('Failed to load sessions:', e)
  }
  console.log('[loadSessions] Returning empty array')
  return [] // Start with empty sessions (ChatGPT style)
}

// Save sessions to localStorage
function saveSessions(sessions: ExtendedSession[]): void {
  try {
    const data = JSON.stringify(sessions)
    localStorage.setItem(SESSIONS_STORAGE_KEY, data)
    console.log('[saveSessions] Saved', sessions.length, 'sessions to localStorage')
  } catch (e) {
    console.error('Failed to save sessions:', e)
  }
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

/**
 * Generate a concise session title from user message
 */
function generateSessionTitle(message: string): string {
  // Remove leading/trailing whitespace
  const trimmed = message.trim()

  // Try to find first sentence or clause (up to punctuation)
  const match = trimmed.match(/^[^。！？，,.\n]+/)
  let title = match ? match[0] : trimmed

  // Limit to 20 characters
  if (title.length > 20) {
    title = title.slice(0, 20) + '...'
  }

  return title || 'New Chat'
}

function App() {
  const [sessions, setSessions] = useState<ExtendedSession[]>(loadSessions)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)
  const [isBestPracticeDrawerOpen, setIsBestPracticeDrawerOpen] = useState(false)

  // Track if this is the initial mount (to prevent saving empty array on mount in StrictMode)
  const isInitialMountRef = useRef(true)

  // Save sessions to localStorage when they change
  useEffect(() => {
    // Skip saving on initial mount in StrictMode to prevent overwriting
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false
      console.log('[saveSessions] Skipping save on initial mount')
      return
    }
    saveSessions(sessions)
  }, [sessions])

  // Track previous chatSteps to detect when they're cleared
  const prevChatStepsRef = useRef<Step[]>([])
  const isSendingRef = useRef(false)

  // Track activePlan for saving to conversation history
  const currentActivePlanRef = useRef<Plan | null>(null)

  // Track timing for current turn
  const currentTurnTimingRef = useRef<{
    startTime: number | null
    firstTokenTime: number | null
  }>({ startTime: null, firstTokenTime: null })

  // Tasks hook for best practices integration
  const {
    templates,
    currentTask,
    createTask,
    createTaskWithInput,
    resumeTask,
    pauseTask,
    cancelTask,
  } = useTasks(currentSessionId)

  // Pending task question state - used to ask user for input before starting task
  // This is separate from askUserQuestion which comes from the backend
  const [pendingTaskQuestion, setPendingTaskQuestion] = useState<{
    question?: string;
    questions?: Array<{
      id: string;
      prompt: string;
      options?: Array<{ id: string; label: string }>;
      allow_multiple?: boolean;
    }>;
    options?: Array<{ id: string; label: string }>;
  } | null>(null)
  const [pendingTemplateId, setPendingTemplateId] = useState<string | null>(null)

  // Chat hook - must be before currentSteps
  const {
    steps: chatSteps,
    sendMessage,
    isStreaming,
    reset,
    firstTokenTime,
    messageSendTime,
    llmOutput,
    artifacts,
    askUserQuestion,
    activePlan,
  } = useChat(currentSessionId)

  // Track timing when messageSendTime or firstTokenTime changes
  useEffect(() => {
    if (messageSendTime) {
      currentTurnTimingRef.current.startTime = messageSendTime
    }
  }, [messageSendTime])

  useEffect(() => {
    if (firstTokenTime) {
      currentTurnTimingRef.current.firstTokenTime = firstTokenTime
    }
  }, [firstTokenTime])

  // Track previous streaming state to detect when response completes
  const prevIsStreamingRef = useRef(false)
  const currentLlmOutputRef = useRef<string | null>(null)

  // Update llmOutput ref when it changes
  useEffect(() => {
    if (llmOutput) {
      currentLlmOutputRef.current = llmOutput
    }
  }, [llmOutput])

  // Update activePlan ref when it changes
  useEffect(() => {
    currentActivePlanRef.current = activePlan
  }, [activePlan])

  const currentSession = useMemo(
    () => sessions.find((s) => s.id === currentSessionId) || null,
    [sessions, currentSessionId]
  )

  // Save completed conversation turn when streaming ends
  // Also don't save when askUserQuestion is set - waiting for user input
  useEffect(() => {
    // Detect when streaming transitions from true to false
    const wasStreaming = prevIsStreamingRef.current
    prevIsStreamingRef.current = isStreaming

    // When streaming ends and we had a conversation
    // Also don't save when askUserQuestion is set - waiting for user input
    if (wasStreaming && !isStreaming && currentSessionId && !askUserQuestion) {
      const currentUserMessage = currentSession?.userMessage || ''
      const timing = currentTurnTimingRef.current
      const output = currentLlmOutputRef.current

      // Only save if we have a user message
      if (!currentUserMessage) return

      // Get steps and summary
      const steps = chatSteps.length > 0 ? chatSteps : prevChatStepsRef.current
      const summary = output || [...steps].reverse().find(s => s.type === 'llm')?.output || null
      const plan = currentActivePlanRef.current

      // Create the turn
      const newTurn: ConversationTurn = {
        id: `turn-${Date.now()}`,
        userMessage: currentUserMessage,
        steps: steps,
        summary,
        timestamp: Date.now(),
        startTime: timing.startTime || undefined,
        firstTokenTime: timing.firstTokenTime,
        endTime: Date.now(),
        plan: plan || undefined,
      }

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSessionId) {
            // Check if this turn already exists (avoid duplicates)
            const turnExists = s.conversationHistory.some(t => t.userMessage === currentUserMessage)
            if (turnExists) return s

            return {
              ...s,
              conversationHistory: [...s.conversationHistory, newTurn],
              stepCount: s.conversationHistory.length + 1,
            }
          }
          return s
        })
      )

      // Clear refs after saving
      prevChatStepsRef.current = []
      currentTurnTimingRef.current = { startTime: null, firstTokenTime: null }
      currentLlmOutputRef.current = null
      currentActivePlanRef.current = null
    }
  }, [isStreaming, currentSessionId, currentSession?.userMessage, chatSteps, askUserQuestion])

  // Combine historical turns with current chat steps
  const displaySteps = useMemo(() => {
    const history = currentSession?.conversationHistory || []
    // Flatten all historical steps and add current steps
    const allSteps: Step[] = []
    history.forEach(turn => {
      allSteps.push(...turn.steps)
    })
    // Add current running steps
    allSteps.push(...chatSteps)
    return allSteps
  }, [currentSession?.conversationHistory, chatSteps])

  const selectedStep = useMemo(
    () => displaySteps.find((s) => s.id === selectedStepId) || null,
    [displaySteps, selectedStepId]
  )

  // Send message handler
  const handleSendMessage = useCallback(
    (message: string, isAskUserAnswer: boolean = false) => {
      // If no current session, create a new one first
      let sessionId = currentSessionId
      if (!sessionId) {
        const newSession: ExtendedSession = {
          id: generateId(),
          title: generateSessionTitle(message),
          stepCount: 0,
          timestamp: Date.now(),
          status: 'active',
          userMessage: message,
          conversationHistory: [],
        }
        setSessions((prev) => [newSession, ...prev])
        sessionId = newSession.id
        setCurrentSessionId(sessionId)
      } else {
        // When answering ask_user, don't save the previous turn yet
        // The answer will be part of the same conversation turn
        if (isAskUserAnswer) {
          // Just update the session timestamp, don't save turn
          setSessions((prev) =>
            prev.map((s) => {
              if (s.id === sessionId) {
                return {
                  ...s,
                  timestamp: Date.now(),
                }
              }
              return s
            })
          )
        } else {
          // Save current turn before starting a new one
          // This includes turns with steps OR turns with askUserQuestion (waiting for user input)
          const hasContentToSave = chatSteps.length > 0 || askUserQuestion !== null
          const currentUserMessage = currentSession?.userMessage || ''

          if (hasContentToSave && currentUserMessage) {
          const currentSteps = chatSteps
          const allStepsCompleted = currentSteps.length === 0 || currentSteps.every(s => s.status === 'completed')
          const summary = llmOutput || [...currentSteps].reverse().find(s => s.type === 'llm')?.output || null

          if (allStepsCompleted) {
            // Get timing info from ref
            const timing = currentTurnTimingRef.current
            const lastStep = currentSteps[currentSteps.length - 1]

            const newTurn: ConversationTurn = {
              id: `turn-${Date.now()}`,
              userMessage: currentUserMessage,
              steps: currentSteps,
              summary: askUserQuestion ? (summary || askUserQuestion.question || '等待用户回复') : summary,
              timestamp: Date.now(),
              startTime: timing.startTime || undefined,
              firstTokenTime: timing.firstTokenTime,
              endTime: lastStep?.endTime || Date.now(),
            }

            // Check if this turn already exists
            const turnExists = currentSession?.conversationHistory?.some(t => t.userMessage === currentUserMessage)

            if (!turnExists) {
              // Add turn to history AND update userMessage in one update
              const title = generateSessionTitle(message)
              setSessions((prev) =>
                prev.map((s) => {
                  if (s.id === sessionId) {
                    return {
                      ...s,
                      conversationHistory: [...s.conversationHistory, newTurn],
                      stepCount: s.conversationHistory.length + 1,
                      userMessage: message,
                      title: s.title === 'New Chat' || s.conversationHistory.length === 0 ? title : s.title,
                      timestamp: Date.now(),
                    }
                  }
                  return s
                })
              )
            } else {
              // Just update the userMessage
              const title = generateSessionTitle(message)
              setSessions((prev) =>
                prev.map((s) => {
                  if (s.id === sessionId) {
                    return {
                      ...s,
                      userMessage: message,
                      title: s.title === 'New Chat' ? title : s.title,
                      timestamp: Date.now(),
                    }
                  }
                  return s
                })
              )
            }

            // Clear refs after saving
            prevChatStepsRef.current = []
            currentTurnTimingRef.current = { startTime: null, firstTokenTime: null }
            currentLlmOutputRef.current = null
          } else {
            // Just update the userMessage without saving turn
            const title = generateSessionTitle(message)
            setSessions((prev) =>
              prev.map((s) => {
                if (s.id === sessionId) {
                  return {
                    ...s,
                    userMessage: message,
                    title: s.title === 'New Chat' || s.conversationHistory.length === 0 ? title : s.title,
                    timestamp: Date.now(),
                  }
                }
                return s
              })
            )
          }
        } else {
          // Just update the userMessage
          const title = generateSessionTitle(message)
          setSessions((prev) =>
            prev.map((s) => {
              if (s.id === sessionId) {
                return {
                  ...s,
                  userMessage: message,
                  title: s.title === 'New Chat' || s.conversationHistory.length === 0 ? title : s.title,
                  timestamp: Date.now(),
                }
              }
              return s
            })
          )
        }
      }
      }
      isSendingRef.current = true
      // Use requestAnimationFrame to ensure the state update is rendered
      // before sending the new message. This prevents the UI from flashing
      // because the historical turn will be rendered first.
      requestAnimationFrame(() => {
        sendMessage(message, undefined, false, isAskUserAnswer)
      })
    },
    [currentSessionId, sendMessage, chatSteps, currentSession, askUserQuestion, llmOutput]
  )

  const handleNewSession = useCallback(() => {
    const newSession: ExtendedSession = {
      id: generateId(),
      title: 'New Chat',
      stepCount: 0,
      timestamp: Date.now(),
      status: 'active',
      userMessage: '',
      conversationHistory: [],
    }
    setSessions((prev) => [newSession, ...prev])
    setCurrentSessionId(newSession.id)
    setSelectedStepId(null)
    reset() // Clear current chat steps
    prevChatStepsRef.current = []
    currentTurnTimingRef.current = { startTime: null, firstTokenTime: null }
  }, [reset])

  const handleDeleteSession = useCallback(
    (id: string) => {
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (currentSessionId === id) {
        setCurrentSessionId(sessions[0]?.id || null)
      }
    },
    [currentSessionId, sessions]
  )

  const handleSelectSession = useCallback((id: string) => {
    // Save current turn before switching
    if (currentSessionId && prevChatStepsRef.current.length > 0 && chatSteps.length > 0) {
      const prevSteps = chatSteps
      const summary = [...prevSteps].reverse().find(s => s.type === 'llm')?.output || null

      // Get timing info from ref
      const timing = currentTurnTimingRef.current
      const lastStep = prevSteps[prevSteps.length - 1]

      const newTurn: ConversationTurn = {
        id: `turn-${Date.now()}`,
        userMessage: currentSession?.userMessage || '',
        steps: prevSteps,
        summary,
        timestamp: Date.now(),
        startTime: timing.startTime || undefined,
        firstTokenTime: timing.firstTokenTime,
        endTime: lastStep?.endTime || undefined,
      }

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSessionId) {
            return {
              ...s,
              conversationHistory: [...s.conversationHistory, newTurn],
              stepCount: s.conversationHistory.length + 1,
            }
          }
          return s
        })
      )
    }

    setCurrentSessionId(id)
    setSelectedStepId(null)
    reset() // Clear current chat steps for the new session
    prevChatStepsRef.current = []
    currentTurnTimingRef.current = { startTime: null, firstTokenTime: null }
  }, [currentSessionId, currentSession?.userMessage, chatSteps, reset])

  // Handler for starting a best practice - creates task and shows task board
  const handleStartBestPractice = useCallback(async (templateId: string) => {
    // Ensure we have a session
    let sessionId = currentSessionId
    if (!sessionId) {
      const newSession: ExtendedSession = {
        id: generateId(),
        title: 'Best Practice Task',
        stepCount: 0,
        timestamp: Date.now(),
        status: 'active',
        userMessage: '',
        conversationHistory: [],
      }
      setSessions((prev) => [newSession, ...prev])
      sessionId = newSession.id
      setCurrentSessionId(sessionId)
    }

    // Close drawer if open
    setIsBestPracticeDrawerOpen(false)

    // Get template info for generating question
    const template = BEST_PRACTICE_TEMPLATES.find(t => t.id === templateId)
    if (template && template.steps.length > 0) {
      // Generate question based on template's first step
      const question = generateTemplateQuestions(
        templateId,
        template.name,
        template.steps[0].name,
        template.steps[0].description
      )
      setPendingTaskQuestion(question)
      setPendingTemplateId(templateId)
    } else {
      // No template info, create task directly
      const task = await createTask(templateId)
      if (task) {
        console.log('[handleStartBestPractice] Task created:', task.id)
      }
    }
  }, [currentSessionId, createTask])

  // Handler for opening all best practices
  const handleOpenAllPractices = useCallback(() => {
    setIsBestPracticeDrawerOpen(true)
  }, [])

  // Handler for answering pending task question
  const handleAnswerTaskQuestion = useCallback(async (answer: string, answerId?: string) => {
    console.log('[handleAnswerTaskQuestion] Answer:', answer, 'AnswerId:', answerId)

    // Clear the question
    setPendingTaskQuestion(null)

    // If user chose to skip, don't create task
    if (answerId === 'skip') {
      setPendingTemplateId(null)
      return
    }

    // Create task with the answer as input payload
    if (pendingTemplateId) {
      const inputPayload: Record<string, unknown> = {
        user_confirmation: answer,
        answer_id: answerId,
      }

      // If user chose to customize, we could show another dialog
      // For now, just create the task
      const task = await createTaskWithInput(pendingTemplateId, inputPayload)
      if (task) {
        console.log('[handleAnswerTaskQuestion] Task created:', task.id)
      }
      setPendingTemplateId(null)
    }
  }, [pendingTemplateId, createTaskWithInput])

  return (
    <>
      <ThreeColumnLayout
        leftSidebar={
          <LeftSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            searchQuery={searchQuery}
            templates={templates}
            onNewSession={handleNewSession}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
            onSearchChange={setSearchQuery}
            onStartBestPractice={handleStartBestPractice}
            onOpenAllPractices={handleOpenAllPractices}
          />
        }
        mainContent={
          <MainContent
            session={currentSession}
            conversationHistory={currentSession?.conversationHistory || []}
            steps={chatSteps}
            allSteps={displaySteps}
            onStepClick={setSelectedStepId}
            onSendMessage={handleSendMessage}
            isStreaming={isStreaming}
            firstTokenTime={firstTokenTime}
            messageSendTime={messageSendTime}
            llmOutput={llmOutput}
            artifacts={artifacts}
            askUserQuestion={askUserQuestion}
            activePlan={activePlan}
            currentTask={currentTask}
            onOpenTaskDetails={() => {}}
            pendingTaskQuestion={pendingTaskQuestion}
            onAnswerTaskQuestion={handleAnswerTaskQuestion}
          />
        }
        detailPanel={currentTask ? (
          <TaskBoard
            task={currentTask}
            onResume={async () => {
              if (currentTask) await resumeTask(currentTask.id)
            }}
            onPause={async () => {
              if (currentTask) await pauseTask(currentTask.id)
            }}
            onCancel={async () => {
              if (currentTask) await cancelTask(currentTask.id)
            }}
            onUpdateStep={async (stepId, output) => {
              console.log('Update step:', stepId, output)
            }}
          />
        ) : selectedStep ? (
          <DetailPanel
            step={selectedStep}
            onClose={() => setSelectedStepId(null)}
          />
        ) : null}
      />
      <Agentation />
      <BestPracticeDrawer
        isOpen={isBestPracticeDrawerOpen}
        onClose={() => setIsBestPracticeDrawerOpen(false)}
        onCreateTask={async (templateId) => {
          console.log('Create task from template:', templateId)
          const task = await createTask(templateId)
          if (task) {
            console.log('Task created successfully:', task.id)
            // Task is now available in the tasks list
          }
        }}
      />
    </>
  )
}

export default App
