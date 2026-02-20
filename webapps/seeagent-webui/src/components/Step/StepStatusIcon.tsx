import type { StepStatus } from '@/types/step'

type StepStatusIconProps = {
  status: StepStatus
}

export function StepStatusIcon({ status }: StepStatusIconProps) {
  switch (status) {
    case 'pending':
      return (
        <div className="w-8 h-8 rounded-full bg-slate-700/50 text-slate-400 border border-slate-600 flex items-center justify-center">
          <span className="material-symbols-outlined text-[18px]">circle</span>
        </div>
      )
    case 'running':
      return (
        <div className="w-8 h-8 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center animate-pulse">
          <span className="material-symbols-outlined text-[18px] animate-spin">sync</span>
        </div>
      )
    case 'completed':
      return (
        <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-500 border border-emerald-500/30 flex items-center justify-center">
          <span className="material-symbols-outlined text-[18px]">check_circle</span>
        </div>
      )
    case 'failed':
      return (
        <div className="w-8 h-8 rounded-full bg-red-500/20 text-red-500 border border-red-500/30 flex items-center justify-center">
          <span className="material-symbols-outlined text-[18px]">cancel</span>
        </div>
      )
  }
}

export default StepStatusIcon
