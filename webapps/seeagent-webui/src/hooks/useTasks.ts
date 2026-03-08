import { useState, useEffect, useCallback } from 'react'
import { apiGet, apiPost } from '@/api/client'
import type { BestPracticeTemplate, OrchestrationTask, TaskStats } from '@/types/task'

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
        setTemplates(data)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch templates:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch templates')
        // Keep empty array on error
        setTemplates([])
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

    try {
      setIsLoading(true)
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
      return null
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

    try {
      setIsLoading(true)
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
      return null
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