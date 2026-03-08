import { useState, useEffect, useCallback } from 'react'
import { apiGet, apiPost } from '@/api/client'
import type { BestPracticeTemplate, OrchestrationTask, TaskStats } from '@/types/task'

// Mock templates for testing when API returns empty or fails
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

// Export for use in other components
export { MOCK_TEMPLATES }

// Helper to create a mock task for testing
function createMockTask(sessionId: string, templateId: string): OrchestrationTask {
  const template = MOCK_TEMPLATES.find(t => t.id === templateId)
  const now = new Date().toISOString()
  const taskId = `task-${Date.now()}`

  return {
    id: taskId,
    session_id: sessionId,
    template_id: templateId,
    name: template?.name || 'Mock Task',
    description: template?.description || 'Mock task for testing',
    status: 'pending',
    current_step_index: 0,
    steps: (template?.steps || []).map((step, index) => ({
      id: `step-${taskId}-${index}`,
      task_id: taskId,
      index,
      name: step.name,
      description: step.description,
      status: 'pending' as const,
      sub_agent_config: {
        name: step.name,
        role: step.description,
        system_prompt: '',
        skills: [],
        mcps: [],
        tools: [],
      },
      input_args: {},
      output_result: {},
      artifacts: [],
      user_feedback: null,
      created_at: now,
      started_at: null,
      finished_at: null,
    })),
    context_variables: {},
    created_at: now,
    updated_at: now,
    completed_at: null,
  }
}

/**
 * Generate a question dialog for a template's first step
 */
export function generateTemplateQuestions(
  _templateId: string,
  templateName: string,
  firstStepName: string,
  firstStepDescription: string
) {
  return {
    question: `即将执行「${templateName}」任务。第一步：${firstStepName} - ${firstStepDescription}。是否开始执行？`,
    options: [
      { id: 'start', label: '开始执行' },
      { id: 'customize', label: '自定义参数' },
      { id: 'skip', label: '取消' },
    ],
  }
}

/**
 * Hook for managing tasks and best practice templates
 */
export function useTasks(sessionId: string | null) {
  const [templates, setTemplates] = useState<BestPracticeTemplate[]>([])
  const [currentTask, setCurrentTask] = useState<OrchestrationTask | null>(null)
  const [tasks, setTasks] = useState<OrchestrationTask[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch best practice templates
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setIsLoading(true)
        const data = await apiGet<BestPracticeTemplate[]>('/best-practices')
        // Use mock data if API returns empty (testing phase)
        setTemplates(data.length > 0 ? data : MOCK_TEMPLATES)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch templates:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch templates')
        // Use mock data on error (testing phase)
        setTemplates(MOCK_TEMPLATES)
      } finally {
        setIsLoading(false)
      }
    }

    fetchTemplates()
  }, [])

  // Fetch task stats
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await apiGet<TaskStats>('/tasks/stats')
        setStats(data)
      } catch (err) {
        console.error('Failed to fetch task stats:', err)
      }
    }

    fetchStats()
  }, [])

  // Create a new task
  const createTask = useCallback(async (templateId: string): Promise<OrchestrationTask | null> => {
    if (!sessionId) {
      console.error('No session ID available')
      return null
    }

    // Check if this is a mock template
    const isMockTemplate = templateId.startsWith('bp-') || MOCK_TEMPLATES.some(t => t.id === templateId)

    try {
      setIsLoading(true)

      // If mock template, create a mock task directly
      if (isMockTemplate) {
        const mockTask = createMockTask(sessionId, templateId)
        setCurrentTask(mockTask)
        setTasks(prev => [mockTask, ...prev])
        return mockTask
      }

      const params = new URLSearchParams({
        session_id: sessionId,
        template_id: templateId,
      })
      const task = await apiGet<OrchestrationTask>(`/tasks?${params}`)
      setCurrentTask(task)
      setTasks(prev => [task, ...prev])
      return task
    } catch (err) {
      console.error('Failed to create task:', err)
      setError(err instanceof Error ? err.message : 'Failed to create task')

      // Fallback to mock task on error
      const mockTask = createMockTask(sessionId, templateId)
      setCurrentTask(mockTask)
      setTasks(prev => [mockTask, ...prev])
      return mockTask
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  // Create a new task with input payload
  const createTaskWithInput = useCallback(async (
    templateId: string,
    inputPayload: Record<string, unknown>
  ): Promise<OrchestrationTask | null> => {
    if (!sessionId) {
      console.error('No session ID available')
      return null
    }

    // Check if this is a mock template
    const isMockTemplate = templateId.startsWith('bp-') || MOCK_TEMPLATES.some(t => t.id === templateId)

    try {
      setIsLoading(true)

      // If mock template, create a mock task directly
      if (isMockTemplate) {
        const mockTask = createMockTask(sessionId, templateId)
        // Merge input payload into context variables
        mockTask.context_variables = { ...mockTask.context_variables, ...inputPayload }
        setCurrentTask(mockTask)
        setTasks(prev => [mockTask, ...prev])
        return mockTask
      }

      const task = await apiPost<OrchestrationTask>('/tasks', {
        session_id: sessionId,
        template_id: templateId,
        input_payload: inputPayload,
      })
      setCurrentTask(task)
      setTasks(prev => [task, ...prev])
      return task
    } catch (err) {
      console.error('Failed to create task with input:', err)
      setError(err instanceof Error ? err.message : 'Failed to create task')

      // Fallback to mock task on error
      const mockTask = createMockTask(sessionId, templateId)
      mockTask.context_variables = { ...mockTask.context_variables, ...inputPayload }
      setCurrentTask(mockTask)
      setTasks(prev => [mockTask, ...prev])
      return mockTask
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  // Resume a task
  const resumeTask = useCallback(async (taskId: string): Promise<void> => {
    try {
      const task = await apiGet<OrchestrationTask>(`/tasks/${taskId}/resume`)
      setCurrentTask(task)
      setTasks(prev => prev.map(t => t.id === taskId ? task : t))
    } catch (err) {
      console.error('Failed to resume task:', err)
      setError(err instanceof Error ? err.message : 'Failed to resume task')
    }
  }, [])

  // Pause a task
  const pauseTask = useCallback(async (taskId: string): Promise<void> => {
    try {
      const task = await apiGet<OrchestrationTask>(`/tasks/${taskId}/pause`)
      setCurrentTask(task)
      setTasks(prev => prev.map(t => t.id === taskId ? task : t))
    } catch (err) {
      console.error('Failed to pause task:', err)
      setError(err instanceof Error ? err.message : 'Failed to pause task')
    }
  }, [])

  // Cancel a task
  const cancelTask = useCallback(async (taskId: string): Promise<void> => {
    try {
      const task = await apiGet<OrchestrationTask>(`/tasks/${taskId}/cancel`)
      setCurrentTask(task)
      setTasks(prev => prev.map(t => t.id === taskId ? task : t))
    } catch (err) {
      console.error('Failed to cancel task:', err)
      setError(err instanceof Error ? err.message : 'Failed to cancel task')
    }
  }, [])

  return {
    templates,
    currentTask,
    tasks,
    stats,
    isLoading,
    error,
    createTask,
    createTaskWithInput,
    resumeTask,
    pauseTask,
    cancelTask,
  }
}