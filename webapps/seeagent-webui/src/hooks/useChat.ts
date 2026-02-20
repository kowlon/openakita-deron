import { useState, useCallback, useRef } from 'react'
import { apiPostStream } from '@/api/client'
import type { ChatRequest, SSEEvent, Step, StepStatus, StepCategory } from '@/types'
import { CORE_STEP_PATTERNS, INTERNAL_STEP_PATTERNS } from '@/types/step'

function generateStepId(): string {
  return `step-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
}

export function useChat(conversationId: string | null) {
  const [steps, setSteps] = useState<Step[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (message: string, endpoint?: string) => {
      if (isStreaming) return

      // Clear previous steps when starting a new message
      setSteps([])
      setIsStreaming(true)
      setError(null)

      const request: ChatRequest = {
        message,
        conversation_id: conversationId || undefined,
        endpoint,
      }

      abortControllerRef.current = new AbortController()

      try {
        await apiPostStream(
          '/chat',
          request,
          (event: Record<string, unknown>) => {
            handleSSEEvent(event as SSEEvent, setSteps)
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

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
    setIsStreaming(false)
  }, [])

  const reset = useCallback(() => {
    setSteps([])
    setError(null)
    setIsStreaming(false)
  }, [])

  return {
    steps,
    isStreaming,
    error,
    sendMessage,
    cancel,
    reset,
  }
}

function handleSSEEvent(
  event: SSEEvent,
  setSteps: React.Dispatch<React.SetStateAction<Step[]>>
) {
  const eventRecord = event as Record<string, unknown>

  switch (event.type) {
    case 'iteration_start': {
      // Iteration start - don't create a step, just mark the beginning
      break
    }

    case 'thinking_start': {
      // Create a thinking/analysis step only if no thinking step exists at all
      setSteps((prev) => {
        const hasThinkingStep = prev.some(s => s.type === 'thinking')
        if (hasThinkingStep) return prev

        const newStep: Step = {
          id: generateStepId(),
          type: 'thinking',
          status: 'running',
          title: '意图分析',
          summary: '正在分析用户请求...',
          startTime: Date.now(),
          category: 'core',
        }
        return [...prev, newStep]
      })
      break
    }

    case 'thinking_delta': {
      // Update thinking step with content
      setSteps((prev) => {
        const lastThinkingStep = [...prev].reverse().find(s => s.type === 'thinking' && s.status === 'running')
        if (lastThinkingStep) {
          return prev.map((step) =>
            step.id === lastThinkingStep.id
              ? { ...step, output: (step.output || '') + (eventRecord.content as string || '') }
              : step
          )
        }
        return prev
      })
      break
    }

    case 'thinking_end': {
      // Don't mark thinking as completed - it may continue in next iteration
      // Just update the summary if needed
      setSteps((prev) =>
        prev.map((step) => {
          if (step.type === 'thinking' && step.status === 'running') {
            return { ...step, summary: '分析完成，准备执行...' }
          }
          return step
        })
      )
      break
    }

    case 'tool_call_start': {
      const toolName = eventRecord.tool as string
      const args = eventRecord.args as Record<string, unknown> | undefined
      // Smart title detection based on tool and args
      const stepTitle = formatToolTitleSmart(toolName, args)
      const stepCategory = categorizeStep(stepTitle, toolName, args)

      setSteps((prev) => {
        // Skip internal steps - don't add them at all
        if (stepCategory === 'internal') {
          return prev
        }

        // Check if the last visible step has the same title - merge them
        const lastCoreStep = [...prev].reverse().find(s => s.category === 'core')
        if (lastCoreStep && lastCoreStep.title === stepTitle && lastCoreStep.status === 'running') {
          // Update existing step with additional input info
          return prev.map((step) =>
            step.id === lastCoreStep.id
              ? { ...step, input: { ...step.input, ...args } }
              : step
          )
        }

        // Create new step
        const newStep: Step = {
          id: (eventRecord.step_id as string) || generateStepId(),
          type: mapToolToStepType(toolName),
          status: 'running',
          title: stepTitle,
          summary: '',
          startTime: Date.now(),
          input: args,
          category: stepCategory,
        }
        return [...prev, newStep]
      })
      break
    }

    case 'tool_call_end': {
      const toolName = eventRecord.tool as string
      const args = eventRecord.args as Record<string, unknown> | undefined
      const stepTitle = formatToolTitleSmart(toolName, args)

      setSteps((prev) =>
        prev.map((step) => {
          // Match by step_id or by title for merged steps
          if (step.id === eventRecord.step_id ||
              (step.status === 'running' && step.title === stepTitle)) {
            const newDuration = Date.now() - step.startTime
            return {
              ...step,
              status: (eventRecord.error ? 'failed' : 'completed') as StepStatus,
              endTime: Date.now(),
              duration: newDuration,
              output: eventRecord.result as string | undefined,
              error: eventRecord.error as string | undefined,
              summary: extractSummary(eventRecord.result as string),
            }
          }
          return step
        })
      )
      break
    }

    case 'text_delta': {
      setSteps((prev) => {
        // Find or create a text step
        const lastStep = prev[prev.length - 1]
        if (lastStep && lastStep.type === 'llm' && lastStep.status === 'running') {
          return prev.map((step, idx) =>
            idx === prev.length - 1
              ? { ...step, output: (step.output || '') + (eventRecord.content as string) }
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
          output: eventRecord.content as string,
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
    case 'plan_created':
    case 'plan_step_updated':
    case 'agent_switch':
    case 'ask_user':
      // These are internal events, don't create visible steps
      break
  }
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
        command.includes('SimpleDocTemplate') || command.includes('python')) {
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

  // ========== CORE OPERATIONS (check first, before internal patterns) ==========

  // Special handling for PDF/Document generation - always show as core
  if (title === 'PDF文件生成' || title === '文档生成' || title === '表格生成') {
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
        command.includes('SimpleDocTemplate') || command.includes('python')) {
      return 'core'
    }
    // Other shell commands - internal
    return 'internal'
  }

  // ========== INTERNAL PATTERNS (check after core operations) ==========

  // Check if it matches internal patterns
  for (const pattern of INTERNAL_STEP_PATTERNS) {
    if (pattern.test(textToCheck)) {
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

  // "执行命令" that's not PDF related - internal
  if (title === '执行命令' || title === '文件写入') {
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

  // Default: hide unknown steps (internal)
  return 'internal'
}

export default useChat
