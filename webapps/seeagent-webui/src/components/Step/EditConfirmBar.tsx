type EditConfirmBarProps = {
  stepTitle: string
  onConfirm: () => void
  onSkip: () => void
  isEditMode: boolean
}

/**
 * Edit mode confirmation bar
 * Shows confirm/skip buttons after a step completes in Edit mode
 */
export function EditConfirmBar({ stepTitle, onConfirm, onSkip, isEditMode }: EditConfirmBarProps) {
  if (!isEditMode) return null

  return (
    <div className="mt-3 p-3 bg-amber-900/20 border border-amber-500/30 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-amber-400 text-lg">edit_note</span>
          <span className="text-xs text-amber-300">
            Edit 模式：步骤「{stepTitle}」已完成，请确认后继续
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onSkip}
            className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
          >
            跳过
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 text-xs font-medium text-white bg-primary hover:bg-primary/80 rounded-lg transition-colors flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">check</span>
            确认，继续下一步
          </button>
        </div>
      </div>
    </div>
  )
}

export default EditConfirmBar
