import { useState, useMemo } from 'react'
import type { Step } from '@/types/step'
import { StepCard } from './StepCard'

type StepTimelineProps = {
  steps: Step[]
  onStepClick: (stepId: string) => void
}

export function StepTimeline({
  steps,
  onStepClick,
}: StepTimelineProps) {
  const [expandedStepIds, setExpandedStepIds] = useState<Set<string>>(new Set())

  // Filter to only show core steps, exclude internal steps and LLM Response (shown in summary)
  const coreSteps = useMemo(
    () => steps.filter((step) => {
      // Exclude internal steps
      if (step.category === 'internal') return false
      // Exclude all LLM type steps - summary text is shown separately in MainContent
      if (step.type === 'llm') return false
      return true
    }),
    [steps]
  )

  const handleToggleExpand = (stepId: string) => {
    setExpandedStepIds((prev) => {
      const next = new Set(prev)
      if (next.has(stepId)) {
        next.delete(stepId)
      } else {
        next.add(stepId)
      }
      return next
    })
  }

  if (coreSteps.length === 0) {
    return null
  }

  return (
    <div className="space-y-0">
      {coreSteps.map((step, index) => (
        <StepCard
          key={step.id}
          step={step}
          index={index}
          isLast={index === coreSteps.length - 1}
          isExpanded={expandedStepIds.has(step.id)}
          onToggleExpand={() => handleToggleExpand(step.id)}
          onClick={() => onStepClick(step.id)}
        />
      ))}
    </div>
  )
}

export default StepTimeline
