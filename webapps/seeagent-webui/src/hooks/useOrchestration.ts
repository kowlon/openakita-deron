import { useState, useEffect, useCallback } from 'react'
import type { Task, TaskListResponse, TaskCreateRequest, TaskConfirmRequest } from '../types/task'
import type { Scenario, ScenarioListResponse } from '../types/scenario'

const API_BASE = 'http://127.0.0.1:18900/api'

/**
 * Hook for fetching and managing tasks
 */
export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchTasks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/tasks`)
      if (!response.ok) throw new Error('Failed to fetch tasks')
      const data: TaskListResponse = await response.json()
      setTasks(data.tasks || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  const createTask = useCallback(async (request: TaskCreateRequest): Promise<Task | null> => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
      if (!response.ok) throw new Error('Failed to create task')
      const task: Task = await response.json()
      setTasks((prev) => [...prev, task])
      return task
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const cancelTask = useCallback(async (taskId: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/tasks/${taskId}/cancel`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error('Failed to cancel task')
      setTasks((prev) =>
        prev.map((t) => (t.task_id === taskId ? { ...t, status: 'cancelled' } : t))
      )
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return false
    }
  }, [])

  const confirmStep = useCallback(
    async (taskId: string, request: TaskConfirmRequest): Promise<boolean> => {
      try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}/confirm`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        })
        if (!response.ok) throw new Error('Failed to confirm step')
        return true
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        return false
      }
    },
    []
  )

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  return {
    tasks,
    loading,
    error,
    fetchTasks,
    createTask,
    cancelTask,
    confirmStep,
  }
}

/**
 * Hook for fetching and managing scenarios
 */
export function useScenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchScenarios = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/scenarios`)
      if (!response.ok) throw new Error('Failed to fetch scenarios')
      const data: ScenarioListResponse = await response.json()
      setScenarios(data.scenarios || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  const startScenario = useCallback(async (scenarioId: string, sessionId?: string): Promise<Task | null> => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/scenarios/${scenarioId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
      if (!response.ok) throw new Error('Failed to start scenario')
      const task: Task = await response.json()
      return task
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchScenarios()
  }, [fetchScenarios])

  return {
    scenarios,
    loading,
    error,
    fetchScenarios,
    startScenario,
  }
}

/**
 * Hook for polling task status
 */
export function useTaskPolling(taskId: string | null, intervalMs: number = 2000) {
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!taskId) {
      setTask(null)
      return
    }

    let mounted = true
    let interval: ReturnType<typeof setInterval>

    const fetchTask = async () => {
      try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`)
        if (!response.ok) return
        const data: Task = await response.json()
        if (mounted) {
          setTask(data)
          setLoading(false)
        }
      } catch {
        // Ignore errors during polling
      }
    }

    setLoading(true)
    fetchTask()
    interval = setInterval(fetchTask, intervalMs)

    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [taskId, intervalMs])

  return { task, loading }
}