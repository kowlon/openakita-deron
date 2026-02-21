import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { ThreeColumnLayout } from './components/Layout/ThreeColumnLayout'
import { LeftSidebar } from './components/Layout/LeftSidebar'
import { MainContent } from './components/Layout/MainContent'
import { DetailPanel } from './components/Layout/DetailPanel'
import { useChat } from './hooks/useChat'
import type { Session, Step, ExecutionMode, ConversationTurn } from './types'

// Extended Session type with conversation history
interface ExtendedSession extends Session {
  conversationHistory: ConversationTurn[]
}

// Storage key for sessions
const SESSIONS_STORAGE_KEY = 'openakita_sessions'

// Load sessions from localStorage
function loadSessions(): ExtendedSession[] {
  try {
    const saved = localStorage.getItem(SESSIONS_STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      return parsed.map((s: ExtendedSession) => ({
        ...s,
        // Ensure timestamp is a number
        timestamp: typeof s.timestamp === 'number' ? s.timestamp : Date.now(),
      }))
    }
  } catch (e) {
    console.error('Failed to load sessions:', e)
  }
  return [] // Start with empty sessions (ChatGPT style)
}

// Save sessions to localStorage
function saveSessions(sessions: ExtendedSession[]): void {
  try {
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions))
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
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('auto')

  // Save sessions to localStorage when they change
  useEffect(() => {
    saveSessions(sessions)
  }, [sessions])

  // Track previous chatSteps to detect when they're cleared
  const prevChatStepsRef = useRef<Step[]>([])
  const isSendingRef = useRef(false)

  // Track timing for current turn
  const currentTurnTimingRef = useRef<{
    startTime: number | null
    firstTokenTime: number | null
  }>({ startTime: null, firstTokenTime: null })

  // Chat hook - must be before currentSteps
  const { steps: chatSteps, sendMessage, isStreaming, reset, firstTokenTime, messageSendTime, llmOutput } = useChat(currentSessionId)

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

  const currentSession = useMemo(
    () => sessions.find((s) => s.id === currentSessionId) || null,
    [sessions, currentSessionId]
  )

  // Save completed conversation turn when streaming ends
  useEffect(() => {
    // Detect when streaming transitions from true to false
    const wasStreaming = prevIsStreamingRef.current
    prevIsStreamingRef.current = isStreaming

    // When streaming ends and we had a conversation
    if (wasStreaming && !isStreaming && currentSessionId) {
      const currentUserMessage = currentSession?.userMessage || ''
      const timing = currentTurnTimingRef.current
      const output = currentLlmOutputRef.current

      // Only save if we have a user message
      if (!currentUserMessage) return

      // Get steps and summary
      const steps = chatSteps.length > 0 ? chatSteps : prevChatStepsRef.current
      const summary = output || [...steps].reverse().find(s => s.type === 'llm')?.output || null

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
    }
  }, [isStreaming, currentSessionId, currentSession?.userMessage, chatSteps])

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
        // Save current turn before starting a new one
        if (chatSteps.length > 0) {
          const currentSteps = chatSteps
          const isCompleted = currentSteps.every(s => s.status === 'completed')
          const summary = [...currentSteps].reverse().find(s => s.type === 'llm')?.output || null
          const currentUserMessage = currentSession?.userMessage || ''

          if (isCompleted && currentUserMessage) {
            // Get timing info from ref
            const timing = currentTurnTimingRef.current
            const lastStep = currentSteps[currentSteps.length - 1]

            const newTurn: ConversationTurn = {
              id: `turn-${Date.now()}`,
              userMessage: currentUserMessage,
              steps: currentSteps,
              summary,
              timestamp: Date.now(),
              startTime: timing.startTime || undefined,
              firstTokenTime: timing.firstTokenTime,
              endTime: lastStep?.endTime || undefined,
            }

            setSessions((prev) =>
              prev.map((s) => {
                if (s.id === sessionId) {
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
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === sessionId) {
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
          conversationHistory={currentSession?.conversationHistory || []}
          steps={chatSteps}
          allSteps={displaySteps}
          executionMode={executionMode}
          onModeChange={setExecutionMode}
          onStepClick={setSelectedStepId}
          onSendMessage={handleSendMessage}
          isStreaming={isStreaming}
          firstTokenTime={firstTokenTime}
          messageSendTime={messageSendTime}
          llmOutput={llmOutput}
        />
      }
      detailPanel={selectedStep ? <DetailPanel step={selectedStep} onClose={() => setSelectedStepId(null)} /> : null}
    />
  )
}

export default App
