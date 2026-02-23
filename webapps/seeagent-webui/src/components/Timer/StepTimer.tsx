import { useState, useEffect, useMemo } from 'react'

type StepTimerProps = {
  startTime: number
  endTime?: number
  isRunning: boolean
}

/**
 * Format milliseconds to seconds string (e.g., "3.25s")
 */
function formatTime(ms: number): string {
  const seconds = ms / 1000
  return `${seconds.toFixed(2)}s`
}

export function StepTimer({ startTime, endTime, isRunning }: StepTimerProps) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    // If completed, calculate final elapsed time
    if (!isRunning && endTime) {
      setElapsed(endTime - startTime)
      return
    }

    // If not running, don't update
    if (!isRunning) {
      return
    }

    // Update every 50ms for smooth display
    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime)
    }, 50)

    return () => clearInterval(interval)
  }, [isRunning, startTime, endTime])

  // Format time
  const formattedTime = useMemo(() => formatTime(elapsed), [elapsed])

  if (isRunning) {
    return (
      <span className="font-mono text-primary tabular-nums animate-pulse">
        {formattedTime}
      </span>
    )
  }

  return (
    <span className="font-mono text-slate-400 tabular-nums">
      {formattedTime}
    </span>
  )
}

export default StepTimer
