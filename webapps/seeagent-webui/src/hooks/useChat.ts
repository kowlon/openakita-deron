import { useState, useCallback, useRef } from 'react'
import { apiPostStream, apiPost } from '@/api/client'
import type { ChatRequest, SSEEvent, Step, StepStatus, StepCategory, Plan, PlanStatus, PlanStepStatus } from '@/types'
import type { Artifact } from '@/types/artifact'
import { CORE_STEP_PATTERNS, INTERNAL_STEP_PATTERNS } from '@/types/step'

function generateStepId(): string {
  return `step-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
}

function generateArtifactId(): string {
  return `artifact-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
}

export function useChat(conversationId: string | null) {
  const [steps, setSteps] = useState<Step[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [pausedStepId, setPausedStepId] = useState<string | null>(null)
  const [pausedStepResult, setPausedStepResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [firstTokenTime, setFirstTokenTime] = useState<number | null>(null)
  const [messageSendTime, setMessageSendTime] = useState<number | null>(null)
  const [llmOutput, setLlmOutput] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [activePlan, setActivePlan] = useState<Plan | null>(null)
  // Ref to track the latest activePlan value for use in SSE event callbacks,
  // avoiding the stale closure problem where the callback captures an outdated activePlan
  const activePlanRef = useRef<Plan | null>(null)
  const [askUserQuestion, setAskUserQuestion] = useState<{
    question?: string;
    questions?: Array<{
      id: string;
      prompt: string;
      options?: Array<{ id: string; label: string }>;
      allow_multiple?: boolean;
    }>;
    options?: Array<{ id: string; label: string }>;
  } | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const editModeRef = useRef(false)

  const sendMessage = useCallback(
    async (message: string, endpoint?: string, editMode: boolean = false, isAskUserAnswer: boolean = false) => {
      console.log('[sendMessage] message:', message, 'isAskUserAnswer:', isAskUserAnswer, 'editMode:', editMode)
      if (isStreaming) return

      // Record message send time immediately
      const sendTime = Date.now()
      setMessageSendTime(sendTime)
      editModeRef.current = editMode

      // When answering ask_user, keep the context (don't reset plan/steps)
      // Otherwise, clear previous state when starting a new message
      if (!isAskUserAnswer) {
        console.log('[sendMessage] Clearing steps and plan (new message)')
        setSteps([])
        setActivePlan(null)
        activePlanRef.current = null
      } else {
        console.log('[sendMessage] Keeping steps and plan (ask_user answer)')
        console.log('[sendMessage] Current steps count:', steps.length, 'Active plan:', activePlan ? 'yes' : 'no')
      }

      setIsStreaming(true)
      setIsPaused(false)
      setPausedStepId(null)
      setPausedStepResult(null)
      setError(null)
      setFirstTokenTime(null) // Reset first token time
      setLlmOutput(null) // Reset LLM output
      setAskUserQuestion(null) // Reset ask user question

      const request: ChatRequest = {
        message,
        conversation_id: conversationId || undefined,
        endpoint,
        edit_mode: editMode,
      }

      abortControllerRef.current = new AbortController()

      try {
        await apiPostStream(
          '/chat',
          request,
          (event: Record<string, unknown>) => {
            handleSSEEvent(
              event as SSEEvent,
              setSteps,
              setFirstTokenTime,
              setLlmOutput,
              setArtifacts,
              setAskUserQuestion,
              setActivePlan,
              activePlanRef,
              editMode,
              (stepId, result) => {
                setIsPaused(true)
                setPausedStepId(stepId)
                setPausedStepResult(result)
                setIsStreaming(false)
              }
            )
          },
          (err) => {
            setError(err.message)
            setIsStreaming(false)
          },
          () => {
            setIsStreaming(false)
          }
        )
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        setIsStreaming(false)
      }
    },
    [conversationId, isStreaming]
  )

  const confirmStep = useCallback(
    async (stepId: string, editedResults?: unknown[], action: 'confirm' | 'skip' = 'confirm') => {
      try {
        const response = await apiPost('/chat/confirm', {
          conversation_id: conversationId,
          step_id: stepId,
          edited_results: editedResults,
          action,
        })
        return response
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to confirm step')
        throw err
      }
    },
    [conversationId]
  )

  const resumeStep = useCallback(
    async (editedResults?: unknown[], endpoint?: string) => {
      if (!conversationId) return

      setIsStreaming(true)
      setIsPaused(false)

      try {
        await apiPostStream(
          '/chat/resume',
          {
            conversation_id: conversationId,
            edited_results: editedResults,
            endpoint,
          },
          (event: Record<string, unknown>) => {
            handleSSEEvent(
              event as SSEEvent,
              setSteps,
              setFirstTokenTime,
              setLlmOutput,
              setArtifacts,
              setAskUserQuestion,
              setActivePlan,
              activePlanRef,
              editModeRef.current,
              (stepId: string, result: string) => {
                setIsPaused(true)
                setPausedStepId(stepId)
                setPausedStepResult(result)
                setIsStreaming(false)
              }
            )
          },
          (err) => {
            setError(err.message)
            setIsStreaming(false)
          },
          () => {
            setIsStreaming(false)
          }
        )
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to resume')
        setIsStreaming(false)
      }
    },
    [conversationId]
  )

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
    setIsStreaming(false)
    setIsPaused(false)
  }, [])

  const reset = useCallback(() => {
    setSteps([])
    setError(null)
    setIsStreaming(false)
    setIsPaused(false)
    setPausedStepId(null)
    setPausedStepResult(null)
    setFirstTokenTime(null)
    setMessageSendTime(null)
    setLlmOutput(null)
    setArtifacts([])
    setAskUserQuestion(null)
    setActivePlan(null)
    activePlanRef.current = null
  }, [])

  return {
    steps,
    isStreaming,
    isPaused,
    pausedStepId,
    pausedStepResult,
    error,
    firstTokenTime,
    messageSendTime,
    llmOutput,
    artifacts,
    activePlan,
    askUserQuestion,
    sendMessage,
    confirmStep,
    resumeStep,
    cancel,
    reset,
  }
}

function handleSSEEvent(
  event: SSEEvent,
  setSteps: React.Dispatch<React.SetStateAction<Step[]>>,
  setFirstTokenTime: React.Dispatch<React.SetStateAction<number | null>>,
  setLlmOutput: React.Dispatch<React.SetStateAction<string | null>>,
  setArtifacts: React.Dispatch<React.SetStateAction<Artifact[]>>,
  setAskUserQuestion: React.Dispatch<React.SetStateAction<{
    question?: string;
    questions?: Array<{
      id: string;
      prompt: string;
      options?: Array<{ id: string; label: string }>;
      allow_multiple?: boolean;
    }>;
    options?: Array<{ id: string; label: string }>;
  } | null>>,
  setActivePlan: React.Dispatch<React.SetStateAction<Plan | null>>,
  activePlanRef: React.MutableRefObject<Plan | null>,
  _editMode: boolean = false,
  onPause?: (stepId: string, result: string) => void
) {
  console.log('[handleSSEEvent] Received event:', event.type, event)
  const eventRecord = event as Record<string, unknown>

  switch (event.type) {
    case 'step_pause': {
      // Edit mode step pause - stop streaming and notify
      const stepId = eventRecord.step_id as string
      const result = eventRecord.result as string | undefined
      if (onPause) {
        onPause(stepId, result || '')
      }
      break
    }
    case 'iteration_start': {
      // Iteration start - don't create a step, just mark the beginning
      break
    }

    case 'thinking_start': {
      // Don't create thinking step automatically - only show steps when tools are actually called
      // For simple Q&A without tool calls, we'll just show the LLM response directly
      break
    }

    case 'first_token': {
      // 收到 first_token 事件，立即锁定 TTFT
      setFirstTokenTime((prev) => prev || Date.now())
      break
    }

    case 'thinking_delta': {
      // Ignore thinking content for now - we don't show thinking steps
      break
    }

    case 'thinking_end': {
      // Ignore thinking end
      break
    }

    case 'tool_call_start': {
      const toolName = eventRecord.tool as string
      const args = eventRecord.args as Record<string, unknown> | undefined
      console.log('[tool_call_start] Tool:', toolName, 'Args:', args)

      // Find current Plan step if Plan is active
      // Priority: in_progress > first pending
      let planStepDescription: string | undefined
      let planStepId: string | undefined
      if (activePlanRef.current) {
        console.log('[tool_call_start] Active plan (from ref):', activePlanRef.current)
        // First try to find in_progress step
        let currentPlanStep = activePlanRef.current.steps.find(s => s.status === 'in_progress')
        // If no in_progress step, find the first pending step (next to execute)
        if (!currentPlanStep) {
          currentPlanStep = activePlanRef.current.steps.find(s => s.status === 'pending')
        }
        console.log('[tool_call_start] Current plan step:', currentPlanStep)
        if (currentPlanStep) {
          planStepDescription = currentPlanStep.description
          planStepId = currentPlanStep.id
          console.log('[tool_call_start] Using plan step:', planStepDescription, 'ID:', planStepId)
        }
      }

      // Use Plan step description if available, otherwise use smart title detection
      const stepTitle = planStepDescription || getToolDisplayName(toolName, args) || formatToolTitleSmart(toolName, args)

      // Determine step category:
      // 1. Plan management tools (create_plan, update_plan_step, complete_plan) are ALWAYS internal
      // 2. For other tools, when associated with a plan step, show as core (the plan step represents
      //    a high-level user-visible task)
      const planManagementTools = ['create_plan', 'update_plan_step', 'complete_plan', 'get_plan_status']
      const isPlanManagementTool = planManagementTools.includes(toolName)
      const stepCategory = isPlanManagementTool ? 'internal' : (planStepId ? 'core' : categorizeStep(stepTitle, toolName, args))
      console.log('[tool_call_start] Title:', stepTitle, 'Category:', stepCategory, 'planStepId:', planStepId, 'isPlanManagementTool:', isPlanManagementTool)

      setSteps((prev) => {
        // Skip internal steps - don't add them at all
        if (stepCategory === 'internal') {
          console.log('[tool_call_start] Skipping internal step:', toolName)
          return prev
        }

        // When we have a planStepId, check if there's already a step for this plan step
        // This prevents creating duplicate steps for the same plan step
        if (planStepId) {
          const existingStepForPlan = prev.find(s =>
            (s.outputData as Record<string, string> | undefined)?.planStepId === planStepId
          )
          if (existingStepForPlan) {
            console.log('[tool_call_start] Step already exists for plan step:', planStepId, 'updating...')
            // Update existing step with new tool info
            return prev.map((step) =>
              step.id === existingStepForPlan.id
                ? { ...step, input: { ...step.input, ...args } }
                : step
            )
          }
        }

        // Check if the last visible step has the same title - merge them
        const lastCoreStep = [...prev].reverse().find(s => s.category === 'core')
        if (lastCoreStep && lastCoreStep.title === stepTitle && lastCoreStep.status === 'running') {
          console.log('[tool_call_start] Merging with existing step:', lastCoreStep.id)
          // Update existing step with additional input info
          return prev.map((step) =>
            step.id === lastCoreStep.id
              ? { ...step, input: { ...step.input, ...args } }
              : step
          )
        }

        // Create new step
        const newStep: Step = {
          id: (eventRecord.id as string) || (eventRecord.step_id as string) || generateStepId(),
          type: mapToolToStepType(toolName),
          status: 'running',
          title: stepTitle,
          summary: '',
          startTime: Date.now(),
          input: args,
          category: stepCategory,
          outputData: planStepId ? { planStepId, originalToolName: toolName } : undefined,
        }
        console.log('[tool_call_start] Adding new step:', newStep)
        return [...prev, newStep]
      })
      break
    }

    case 'tool_call_end': {
      const toolName = eventRecord.tool as string
      const args = eventRecord.args as Record<string, unknown> | undefined
      const stepTitle = getToolDisplayName(toolName, args) || formatToolTitleSmart(toolName, args)
      const result = eventRecord.result as string | undefined

      // Detect file creation from tool result and create artifact
      const artifact = extractArtifactFromToolResult(toolName, args, result)
      if (artifact) {
        setArtifacts((prev) => [...prev, artifact])
      }

      setSteps((prev) => {
        // Use first-match strategy to avoid updating multiple steps
        // when they share the same originalToolName or title
        let matched = false
        return prev.map((step) => {
          if (matched) return step
          // Match by id/step_id first
          const eventId = (eventRecord.id as string) || (eventRecord.step_id as string)
          // Also match by title (for merged steps) or by originalToolName (for plan-described steps)
          const matchesById = step.id === eventId
          const matchesByTitle = step.status === 'running' && step.title === stepTitle
          const matchesByOriginalTool = step.status === 'running' &&
            (step.outputData as Record<string, string> | undefined)?.originalToolName === toolName
          if (matchesById || matchesByTitle || matchesByOriginalTool) {
            matched = true
            const newDuration = Date.now() - step.startTime
            return {
              ...step,
              status: (eventRecord.error ? 'failed' : 'completed') as StepStatus,
              endTime: Date.now(),
              duration: newDuration,
              output: result,
              error: eventRecord.error as string | undefined,
              summary: extractSummary(result),
            }
          }
          return step
        })
      })
      break
    }

    case 'text_delta': {
      const content = eventRecord.content as string || ''
      console.log('[text_delta] Content:', content.substring(0, 50) + (content.length > 50 ? '...' : ''))

      // Record first token time (only once) - fallback for backwards compatibility
      setFirstTokenTime((prev) => prev || Date.now())

      // Always update llmOutput (for conversation history)
      setLlmOutput((prev) => (prev || '') + content)

      // Only create/update LLM step if there are already other steps (complex task)
      // For simple Q&A without tool calls, we don't show step cards
      setSteps((prev) => {
        // If no previous steps, don't create any step (simple Q&A)
        if (prev.length === 0) {
          return prev
        }

        // Find or create a text step (for complex tasks with tool calls)
        const lastStep = prev[prev.length - 1]
        if (lastStep && lastStep.type === 'llm' && lastStep.status === 'running') {
          return prev.map((step, idx) =>
            idx === prev.length - 1
              ? { ...step, output: (step.output || '') + content }
              : step
          )
        }
        // Create new text step (LLM response is always core)
        const newStep: Step = {
          id: generateStepId(),
          type: 'llm',
          status: 'running',
          title: '总结',
          summary: '',
          startTime: Date.now(),
          output: content,
          category: 'core',
        }
        return [...prev, newStep]
      })
      break
    }

    case 'done': {
      setSteps((prev) =>
        prev.map((step) =>
          step.status === 'running'
            ? { ...step, status: 'completed' as StepStatus, endTime: Date.now(), duration: Date.now() - step.startTime }
            : step
        )
      )
      break
    }

    case 'error': {
      setSteps((prev) => {
        const lastStep = prev[prev.length - 1]
        if (lastStep && lastStep.status === 'running') {
          return prev.map((step, idx) =>
            idx === prev.length - 1
              ? { ...step, status: 'failed' as StepStatus, error: eventRecord.message as string }
              : step
          )
        }
        return prev
      })
      break
    }

    // Handle other event types (plan_created, plan_step_updated, etc.)
    case 'plan_created': {
      console.log('[plan_created] Raw event:', eventRecord)
      const raw = eventRecord.plan as Record<string, unknown> | undefined
      console.log('[plan_created] Raw plan data:', raw)
      if (raw) {
        const plan: Plan = {
          id: (raw.id as string) || '',
          task_summary: (raw.taskSummary as string) || (raw.task_summary as string) || '',
          steps: ((raw.steps as Array<Record<string, unknown>>) || []).map((s) => ({
            id: String(s.id || ''),
            description: String(s.description || ''),
            status: (s.status as PlanStepStatus) || 'pending',
          })),
          status: (raw.status as PlanStatus) || 'in_progress',
          created_at: new Date().toISOString(),
        }
        console.log('[plan_created] Mapped plan:', plan)
        console.log('[plan_created] Calling setActivePlan')
        setActivePlan(plan)
        activePlanRef.current = plan
        console.log('[plan_created] Calling setSteps([]) to clear pre-plan steps')
        // Clear pre-plan steps (failed attempts before plan was created)
        setSteps([])
      } else {
        console.warn('[plan_created] No plan data in event')
      }
      break
    }

    case 'plan_step_updated': {
      // Backend sends stepId (camelCase)
      const stepId = (eventRecord.stepId as string) || (eventRecord.step_id as string)
      const status = eventRecord.status as string
      const result = eventRecord.result as string
      console.log('[plan_step_updated] Updating step:', stepId, 'to status:', status)

      const updateSteps = (plan: Plan): Plan => ({
        ...plan,
        steps: plan.steps.map((s) =>
          s.id === stepId
            ? {
                ...s,
                status: (status as PlanStepStatus) || s.status,
                result: result || s.result,
                completed_at: ['completed', 'failed', 'skipped'].includes(status)
                  ? new Date().toISOString()
                  : s.completed_at,
              }
            : s
        ),
      })

      // Update ref synchronously so subsequent SSE events (e.g. tool_call_start)
      // see the latest plan state immediately, before React flushes batched updates
      if (activePlanRef.current) {
        activePlanRef.current = updateSteps(activePlanRef.current)
      }

      // Update React state for re-rendering
      setActivePlan((prev) => prev ? updateSteps(prev) : null)
      break
    }

    case 'plan_completed': {
      console.log('[plan_completed] Plan completed event received')
      const summary = eventRecord.summary as string | undefined

      // Update ref synchronously
      if (activePlanRef.current) {
        activePlanRef.current = {
          ...activePlanRef.current,
          status: 'completed' as PlanStatus,
          summary: summary || activePlanRef.current.summary,
          completed_at: new Date().toISOString(),
        }
      }

      // Update React state for re-rendering
      setActivePlan((prev) => prev ? {
        ...prev,
        status: 'completed' as PlanStatus,
        summary: summary || prev.summary,
        completed_at: new Date().toISOString(),
      } : null)
      break
    }

    case 'agent_switch':
      // These are internal events, don't create visible steps
      break

    case 'ask_user': {
      // Handle ask_user event - store the question for UI to display
      const question = eventRecord.question as string || ''
      const options = eventRecord.options as Array<{ id: string; label: string }> | undefined
      const questions = eventRecord.questions as Array<{
        id: string;
        prompt: string;
        options?: Array<{ id: string; label: string }>;
        allow_multiple?: boolean;
      }> | undefined

      if (question || questions) {
        setAskUserQuestion({ question, options, questions })
      }
      break
    }

    case 'artifact_created': {
      // Handle artifact creation event
      const artifactData = eventRecord.artifact as Record<string, unknown> | undefined
      if (artifactData) {
        const newArtifact: Artifact = {
          id: (artifactData.id as string) || generateArtifactId(),
          type: artifactData.type as Artifact['type'] || 'other',
          filename: (artifactData.filename as string) || (artifactData.name as string) || 'Unknown file',
          filepath: (artifactData.filepath as string) || (artifactData.path as string) || '',
          size: artifactData.size as number | undefined,
          downloadUrl: artifactData.downloadUrl as string | undefined,
          createdAt: Date.now(),
          description: artifactData.description as string | undefined,
        }
        setArtifacts((prev) => [...prev, newArtifact])
      }
      break
    }
  }
}

/**
 * Tool display name mapping - user-friendly names for tools
 */
const TOOL_DISPLAY_NAMES: Record<string, string> = {
  // Browser tools
  'browser_navigate': '打开网页',
  'browser_task': '执行浏览器操作',
  'browser_screenshot': '截图保存',
  'browser_click': '点击元素',
  'browser_type': '输入文本',
  'browser_scroll': '滚动页面',
  'browser_snapshot': '获取页面快照',

  // Search tools
  'web_search': '网络搜索',
  'search': '搜索',
  'news_search': '新闻搜索',
  'image_search': '图片搜索',
  'video_search': '视频搜索',

  // File tools
  'write_file': '写入文件',
  'read_file': '读取文件',
  'Write': '写入文件',
  'Read': '读取文件',

  // Plan tools
  'create_plan': '创建计划',
  'update_plan_step': '更新计划步骤',
  'complete_plan': '完成计划',
  'get_plan_status': '获取计划状态',

  // Other tools
  'deliver_artifacts': '交付结果',
  'pdf': 'PDF 处理',
  'run_shell': '执行命令',
  'Bash': '执行命令',
  'get_skill_info': '获取技能信息',
}

/**
 * Get user-friendly tool display name with smart parameter-based optimization
 */
function getToolDisplayName(toolName: string, args?: Record<string, unknown>, planStepDescription?: string): string {
  // Priority 1: Use Plan step description if available
  if (planStepDescription) {
    return planStepDescription
  }

  // Priority 2: Smart optimization based on tool and args
  if (toolName === 'browser_navigate' && args?.url) {
    const url = args.url as string
    try {
      const hostname = new URL(url).hostname
      if (hostname.includes('baidu.com')) {
        return '打开百度首页'
      } else if (hostname.includes('google.com')) {
        return '打开Google'
      } else {
        return `打开 ${hostname}`
      }
    } catch {
      return '打开网页'
    }
  }

  if (toolName === 'web_search' && args?.query) {
    return `搜索"${args.query}"`
  }

  if (toolName === 'browser_screenshot' && args?.path) {
    return '截图保存'
  }

  // Priority 3: Use mapping table
  return TOOL_DISPLAY_NAMES[toolName] || toolName
}

/**
 * Format tool name to readable Chinese title
 */
function formatToolTitle(tool: string | undefined): string {
  if (!tool) return '处理中'

  const toolTitles: Record<string, string> = {
    'web_search': '网络搜索',
    'search': '搜索',
    'news_search': '新闻搜索',
    'image_search': '图片搜索',
    'video_search': '视频搜索',
    'create_plan': '创建计划',
    'update_plan_step': '更新计划步骤',
    'complete_plan': '完成计划',
    'get_skill_info': '获取技能信息',
    'deliver_artifacts': '交付结果',
    'pdf': 'PDF 处理',
    'read_file': '文件读取',
    'write_file': '文件写入',
    'run_shell': '执行命令',
  }

  return toolTitles[tool] || tool
}

/**
 * Smart title formatting that considers tool args to generate meaningful titles
 */
function formatToolTitleSmart(tool: string | undefined, args: Record<string, unknown> | undefined): string {
  if (!tool) return '处理中'

  // Check for PDF generation
  if (tool === 'write_file' || tool === 'Write') {
    const filePath = (args?.file_path as string) || (args?.path as string) || ''
    const content = (args?.content as string) || ''

    // If writing a PDF file or PDF generation script
    if (filePath.endsWith('.pdf') || content.includes('reportlab') || content.includes('SimpleDocTemplate') || content.includes('PDF')) {
      return 'PDF文件生成'
    }
    // If writing other document types
    if (filePath.endsWith('.docx') || filePath.endsWith('.doc')) {
      return '文档生成'
    }
    if (filePath.endsWith('.xlsx') || filePath.endsWith('.xls')) {
      return '表格生成'
    }
    return '文件写入'
  }

  // Check for shell execution that might be document/PDF generation
  if (tool === 'run_shell' || tool === 'Bash' || tool === 'execute_command') {
    const command = (args?.command as string) || ''
    // PDF or document generation scripts
    if (command.includes('.pdf') || command.includes('reportlab') ||
        command.includes('SimpleDocTemplate')) {
      return 'PDF文件生成'
    }
    if (command.includes('.docx') || command.includes('.doc')) {
      return '文档生成'
    }
    return '执行命令'
  }

  // For search tools, return formatted title
  if (tool.includes('search')) {
    return formatToolTitle(tool)
  }

  return formatToolTitle(tool)
}

function mapToolToStepType(tool: string): Step['type'] {
  if (tool?.includes('search') || tool?.includes('web')) return 'tool'
  if (tool?.includes('think') || tool?.includes('reason')) return 'thinking'
  if (tool?.includes('plan')) return 'planning'
  return 'skill'
}

function extractSummary(result: string | undefined): string {
  if (!result) return ''
  try {
    const parsed = JSON.parse(result)
    if (parsed.summary) return parsed.summary
    if (parsed.message) return parsed.message
    return ''
  } catch {
    return result.slice(0, 200)
  }
}

/**
 * Categorize a step as 'core' or 'internal' based on its title, tool name, and args
 */
function categorizeStep(title: string, tool?: string, args?: Record<string, unknown>): StepCategory {
  const textToCheck = `${title} ${tool || ''}`.toLowerCase()
  const toolLower = (tool || '').toLowerCase()

  // ========== CORE OPERATIONS (check first, before internal patterns) ==========

  // Special handling for PDF/Document generation - always show as core
  if (title === 'PDF文件生成' || title === '文档生成' || title === '表格生成') {
    return 'core'
  }

  // Browser tools are always core - check before internal patterns to avoid
  // false matches on domain names (e.g., navigating to config.example.com
  // should not be caught by /config/i internal pattern)
  if (tool?.startsWith('browser_')) {
    return 'core'
  }

  // Check if write_file is writing something meaningful
  if (tool === 'write_file' || tool === 'Write') {
    const filePath = (args?.file_path as string) || (args?.path as string) || ''
    const content = (args?.content as string) || ''

    // PDF or document generation - core
    if (filePath.endsWith('.pdf') || content.includes('reportlab') || content.includes('SimpleDocTemplate') || content.includes('PDF')) {
      return 'core'
    }
  }

  // Check if run_shell is for PDF/document generation - core
  if (tool === 'run_shell' || tool === 'Bash' || tool === 'execute_command') {
    const command = (args?.command as string) || ''
    // PDF or document generation scripts - core
    if (command.includes('reportlab') || command.includes('.pdf') ||
        command.includes('SimpleDocTemplate') || command.includes('.docx') ||
        command.includes('.xlsx')) {
      return 'core'
    }
    // Other shell commands - internal
    return 'internal'
  }

  // ========== INTERNAL PATTERNS (check after core operations) ==========

  // Check raw tool name against internal patterns (anchored patterns like ^create_plan$ need raw tool name)
  for (const pattern of INTERNAL_STEP_PATTERNS) {
    if (pattern.test(toolLower) || pattern.test(textToCheck)) {
      return 'internal'
    }
  }

  // Check if write_file is for temp files - internal
  if (tool === 'write_file' || tool === 'Write') {
    const filePath = (args?.file_path as string) || (args?.path as string) || ''
    if (filePath.includes('temp') || filePath.includes('.tmp') || filePath.includes('cache')) {
      return 'internal'
    }
  }

  // Read/read_file tools are always internal
  if (tool === 'read_file' || tool === 'Read') {
    return 'internal'
  }

  // Internal tool display names - "执行命令", "写入文件", "读取文件", "文件写入" are all internal
  if (title === '执行命令' || title === '文件写入' || title === '写入文件' || title === '读取文件') {
    return 'internal'
  }

  // ========== CORE PATTERNS (check for other core operations) ==========

  // Check if it matches core patterns
  for (const pattern of CORE_STEP_PATTERNS) {
    if (pattern.test(textToCheck)) {
      return 'core'
    }
  }

  // LLM Response is treated as core (but will be shown in summary section)
  if (tool?.includes('llm') || title.toLowerCase().includes('response')) {
    return 'core'
  }

  // Default: show unknown steps as core (unless explicitly marked as internal)
  return 'core'
}

/**
 * Extract artifact information from tool result
 * Detects when files are created and returns artifact metadata
 */
function extractArtifactFromToolResult(
  toolName: string,
  args: Record<string, unknown> | undefined,
  result: string | undefined
): Artifact | null {
  // Check for write_file tool
  if (toolName === 'write_file' || toolName === 'Write') {
    const filePath = (args?.file_path as string) || (args?.path as string) || ''
    const filename = filePath.split('/').pop() || filePath.split('\\').pop() || 'Unknown file'

    // Only create artifacts for meaningful files (not temp files)
    if (filePath &&
        !filePath.includes('temp') &&
        !filePath.includes('.tmp') &&
        !filePath.includes('cache') &&
        !filePath.includes('__pycache__')) {
      return {
        id: `artifact-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        type: getArtifactTypeFromExtension(filename),
        filename,
        filepath: filePath,
        size: undefined,
        downloadUrl: `/api/files/download?path=${encodeURIComponent(filePath)}`,
        createdAt: Date.now(),
      }
    }
  }

  // Check for shell/Bash commands that might create files
  if (toolName === 'run_shell' || toolName === 'Bash' || toolName === 'execute_command') {
    const command = (args?.command as string) || ''
    const resultText = result || ''

    // Check if result contains file path mentions (e.g., "written to", "saved to", "created")
    const filePatterns = [
      /(?:written|saved|created|generated)\s+(?:to|as)\s+[`"']?([^\s`"']+\.(?:pdf|docx?|xlsx?|png|jpg|jpeg|gif|txt|md|py|js|ts|html|css))[`"']?/i,
      /(?:file|output)\s*:\s*[`"']?([^\s`"']+\.(?:pdf|docx?|xlsx?|png|jpg|jpeg|gif|txt|md|py|js|ts|html|css))[`"']?/i,
    ]

    for (const pattern of filePatterns) {
      const match = resultText.match(pattern)
      if (match && match[1]) {
        const filePath = match[1]
        const filename = filePath.split('/').pop() || filePath.split('\\').pop() || filePath
        return {
          id: `artifact-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          type: getArtifactTypeFromExtension(filename),
          filename,
          filepath: filePath,
          size: undefined,
          downloadUrl: `/api/files/download?path=${encodeURIComponent(filePath)}`,
          createdAt: Date.now(),
        }
      }
    }

    // Check if command creates a PDF file
    if (command.includes('.pdf') || resultText.includes('.pdf')) {
      const pdfMatch = resultText.match(/[^\s`"']+\.pdf/i) || command.match(/[^\s`"']+\.pdf/i)
      if (pdfMatch) {
        const filePath = pdfMatch[0]
        const filename = filePath.split('/').pop() || filePath
        return {
          id: `artifact-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          type: 'pdf',
          filename,
          filepath: filePath,
          size: undefined,
          downloadUrl: `/api/files/download?path=${encodeURIComponent(filePath)}`,
          createdAt: Date.now(),
        }
      }
    }
  }

  return null
}

/**
 * Get artifact type from file extension
 */
function getArtifactTypeFromExtension(filename: string): Artifact['type'] {
  const ext = filename.split('.').pop()?.toLowerCase() || ''

  const typeMap: Record<string, Artifact['type']> = {
    'pdf': 'pdf',
    'doc': 'word',
    'docx': 'word',
    'xls': 'excel',
    'xlsx': 'excel',
    'csv': 'excel',
    'jpg': 'image',
    'jpeg': 'image',
    'png': 'image',
    'gif': 'image',
    'svg': 'image',
    'webp': 'image',
    'js': 'code',
    'ts': 'code',
    'jsx': 'code',
    'tsx': 'code',
    'py': 'code',
    'java': 'code',
    'cpp': 'code',
    'c': 'code',
    'go': 'code',
    'rs': 'code',
    'html': 'code',
    'css': 'code',
    'json': 'code',
    'xml': 'code',
    'yaml': 'code',
    'yml': 'code',
    'md': 'code',
    'txt': 'text',
    'log': 'text',
  }

  return typeMap[ext] || 'other'
}

export default useChat
