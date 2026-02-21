import { useState, useEffect, useMemo } from 'react'

type ElapsedTimerProps = {
  startTime: number | null
  firstTokenTime: number | null
  isRunning: boolean
  isCompleted: boolean
  endTime?: number | null
}

/**
 * Format milliseconds to seconds string (e.g., "3.25s")
 */
function formatTime(ms: number | null): string {
  if (ms === null || ms === undefined) return '0.00s'
  const seconds = ms / 1000
  return `${seconds.toFixed(2)}s`
}

export function ElapsedTimer({
  startTime,
  firstTokenTime,
  isRunning,
  isCompleted,
  endTime
}: ElapsedTimerProps) {
  const [currentElapsed, setCurrentElapsed] = useState(0)

  // Update elapsed time while running
  useEffect(() => {
    if (!startTime) {
      setCurrentElapsed(0)
      return
    }

    // Reset to 0 when startTime changes (new message)
    setCurrentElapsed(0)

    // If completed, calculate final elapsed time
    if (isCompleted && endTime) {
      setCurrentElapsed(endTime - startTime)
      return
    }

    // If not running, don't update
    if (!isRunning) {
      return
    }

    // Update every 50ms for smooth display
    const interval = setInterval(() => {
      setCurrentElapsed(Date.now() - startTime)
    }, 50)

    return () => clearInterval(interval)
  }, [isRunning, isCompleted, startTime, endTime])

  // Calculate TTFT (Time to First Token)
  const ttft = useMemo(() => {
    if (!firstTokenTime || !startTime) return null
    return firstTokenTime - startTime
  }, [firstTokenTime, startTime])

  // Calculate total time
  const totalTime = useMemo(() => {
    if (isCompleted && endTime && startTime) {
      return endTime - startTime
    }
    return currentElapsed
  }, [isCompleted, endTime, startTime, currentElapsed])

  // Don't render if never started
  if (!startTime) {
    return null
  }

  // Render completed state
  if (isCompleted) {
    return (
      <div className="inline-flex items-center gap-2 text-xs text-slate-500">
        <span className="font-mono tabular-nums">
          TTFT: {formatTime(ttft)}
        </span>
        <span className="text-slate-600">|</span>
        <span className="font-mono tabular-nums">
          总计: {formatTime(totalTime)}
        </span>
      </div>
    )
  }

  // Render running state - TTFT counts from 0 until first token arrives
  return (
    <div className="inline-flex items-center gap-2 text-xs">
      <div className="relative">
        <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
        <div className="absolute inset-0 w-2 h-2 bg-primary rounded-full animate-ping" />
      </div>
      <span className="font-mono text-primary tabular-nums">
        TTFT: {ttft !== null ? formatTime(ttft) : formatTime(currentElapsed)}
      </span>
      <span className="text-slate-600">|</span>
      <span className="font-mono text-slate-400 tabular-nums">
        总计: {formatTime(totalTime)}
      </span>
    </div>
  )
}

export default ElapsedTimer
