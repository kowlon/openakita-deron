import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { ThreeColumnLayout } from './components/Layout/ThreeColumnLayout'
import { LeftSidebar } from './components/Layout/LeftSidebar'
import { MainContent } from './components/Layout/MainContent'
import { DetailPanel } from './components/Layout/DetailPanel'
import { useChat } from './hooks/useChat'
import type { Session, Step, ExecutionMode } from './types'

// Conversation turn type
interface ConversationTurn {
  id: string
  userMessage: string
  steps: Step[]
  summary: string | null
  timestamp: number
}

// Extended Session type with conversation history
interface ExtendedSession extends Session {
  conversationHistory: ConversationTurn[]
}

// Mock sessions
const MOCK_SESSIONS: ExtendedSession[] = [
  {
    id: 'session-1',
    title: 'Web Research Task',
    stepCount: 3,
    timestamp: Date.now() - 60000,
    status: 'active',
    userMessage: 'Research the latest trends in AI agents for 2024. Focus on multi-agent orchestration frameworks.',
    conversationHistory: [],
  },
  {
    id: 'session-2',
    title: 'Data Extraction',
    stepCount: 1,
    timestamp: Date.now() - 3600000,
    status: 'completed',
    userMessage: 'Extract all email addresses from the provided document.',
    conversationHistory: [],
  },
  {
    id: 'session-3',
    title: 'Market Analysis',
    stepCount: 5,
    timestamp: Date.now() - 86400000,
    status: 'completed',
    userMessage: 'Analyze the competitive landscape for AI coding assistants.',
    conversationHistory: [],
  },
]

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
  const [sessions, setSessions] = useState<ExtendedSession[]>(MOCK_SESSIONS)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>('session-1')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('auto')

  // Track previous chatSteps to detect when they're cleared
  const prevChatStepsRef = useRef<Step[]>([])
  const isSendingRef = useRef(false)

  // Chat hook - must be before currentSteps
  const { steps: chatSteps, sendMessage, isStreaming, reset } = useChat(currentSessionId)

  const currentSession = useMemo(
    () => sessions.find((s) => s.id === currentSessionId) || null,
    [sessions, currentSessionId]
  )

  // Save completed conversation turn when chatSteps transition from non-empty to empty
  useEffect(() => {
    // Update ref when steps change
    if (chatSteps.length > 0) {
      prevChatStepsRef.current = chatSteps
    }

    // When steps are cleared and we had previous steps, save the turn
    if (currentSessionId && chatSteps.length === 0 && !isStreaming && prevChatStepsRef.current.length > 0) {
      const prevSteps = prevChatStepsRef.current
      const summary = [...prevSteps].reverse().find(s => s.type === 'llm')?.output || null
      const prevUserMessage = currentSession?.userMessage || ''

      // Only save if steps are actually completed
      const isCompleted = prevSteps.every(s => s.status === 'completed')
      if (!isCompleted) return

      const newTurn: ConversationTurn = {
        id: `turn-${Date.now()}`,
        userMessage: prevUserMessage,
        steps: prevSteps,
        summary,
        timestamp: Date.now(),
      }

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSessionId) {
            // Check if this turn already exists (avoid duplicates)
            const turnExists = s.conversationHistory.some(t => t.userMessage === prevUserMessage)
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

      // Clear the ref after saving
      prevChatStepsRef.current = []
    }
  }, [chatSteps.length, chatSteps, isStreaming, currentSessionId, currentSession?.userMessage])

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
    (message: string) => {
      // Save current turn before starting a new one
      if (currentSessionId && chatSteps.length > 0) {
        const currentSteps = chatSteps
        const isCompleted = currentSteps.every(s => s.status === 'completed')
        const summary = [...currentSteps].reverse().find(s => s.type === 'llm')?.output || null
        const currentUserMessage = currentSession?.userMessage || ''

        if (isCompleted && currentUserMessage) {
          const newTurn: ConversationTurn = {
            id: `turn-${Date.now()}`,
            userMessage: currentUserMessage,
            steps: currentSteps,
            summary,
            timestamp: Date.now(),
          }

          setSessions((prev) =>
            prev.map((s) => {
              if (s.id === currentSessionId) {
                // Check if this turn already exists
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
        }
      }

      // Update current session with user message and generate title
      if (currentSessionId) {
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === currentSessionId) {
              // Generate title from user message (first 30 chars or until first punctuation)
              const title = generateSessionTitle(message)
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
      isSendingRef.current = true
      sendMessage(message)
    },
    [currentSessionId, sendMessage, chatSteps, currentSession?.userMessage]
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

      const newTurn: ConversationTurn = {
        id: `turn-${Date.now()}`,
        userMessage: currentSession?.userMessage || '',
        steps: prevSteps,
        summary,
        timestamp: Date.now(),
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
  }, [currentSessionId, currentSession?.userMessage, chatSteps, reset])

  return (
    <ThreeColumnLayout
      leftSidebar={
        <LeftSidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          searchQuery={searchQuery}
          onNewSession={handleNewSession}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          onSearchChange={setSearchQuery}
        />
      }
      mainContent={
        <MainContent
          session={currentSession}
          steps={displaySteps}
          executionMode={executionMode}
          onModeChange={setExecutionMode}
          onStepClick={setSelectedStepId}
          onSendMessage={handleSendMessage}
        />
      }
      detailPanel={selectedStep ? <DetailPanel step={selectedStep} onClose={() => setSelectedStepId(null)} /> : null}
    />
  )
}

export default App
