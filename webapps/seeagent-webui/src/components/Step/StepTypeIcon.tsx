import type { StepType } from '@/types/step'

type StepTypeIconProps = {
  type: StepType
  size?: number
}

export function StepTypeIcon({ type, size = 20 }: StepTypeIconProps) {
  const iconClass = `text-[${size}px]`

  switch (type) {
    case 'llm':
      return (
        <span className={`material-symbols-outlined text-blue-400 ${iconClass}`} style={{ fontSize: size }}>
          psychology
        </span>
      )
    case 'tool':
      return (
        <span className={`material-symbols-outlined text-orange-400 ${iconClass}`} style={{ fontSize: size }}>
          build
        </span>
      )
    case 'skill':
      return (
        <span className={`material-symbols-outlined text-purple-400 ${iconClass}`} style={{ fontSize: size }}>
          bolt
        </span>
      )
    case 'thinking':
      return (
        <span className={`material-symbols-outlined text-yellow-400 ${iconClass}`} style={{ fontSize: size }}>
          lightbulb
        </span>
      )
    case 'planning':
      return (
        <span className={`material-symbols-outlined text-green-400 ${iconClass}`} style={{ fontSize: size }}>
          list
        </span>
      )
  }
}

export default StepTypeIcon
