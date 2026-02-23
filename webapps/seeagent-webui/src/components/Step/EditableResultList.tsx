import { useState, useCallback } from 'react'
import { EditableResultCard, type EditableResult } from './EditableResultCard'

type EditableResultListProps = {
  results: EditableResult[]
  onChange: (results: EditableResult[]) => void
  onConfirm?: () => void
  isEditMode?: boolean
}

/**
 * Editable result list component
 * Manages multiple editable result cards with add custom content feature
 */
export function EditableResultList({
  results,
  onChange,
  onConfirm,
  isEditMode = false,
}: EditableResultListProps) {
  const [isAddingCustom, setIsAddingCustom] = useState(false)
  const [customTitle, setCustomTitle] = useState('')
  const [customContent, setCustomContent] = useState('')

  const handleToggleSelect = useCallback(
    (id: string) => {
      onChange(
        results.map((r) =>
          r.id === id ? { ...r, selected: !r.selected } : r
        )
      )
    },
    [results, onChange]
  )

  const handleDelete = useCallback(
    (id: string) => {
      onChange(results.filter((r) => r.id !== id))
    },
    [results, onChange]
  )

  const handleEdit = useCallback(
    (id: string, updates: Partial<EditableResult>) => {
      onChange(
        results.map((r) => (r.id === id ? { ...r, ...updates } : r))
      )
    },
    [results, onChange]
  )

  const handleAddCustom = useCallback(() => {
    if (!customTitle.trim() || !customContent.trim()) return

    const newResult: EditableResult = {
      id: `custom-${Date.now()}`,
      title: customTitle.trim(),
      content: customContent.trim(),
      source: 'User Added',
      selected: true,
    }

    onChange([...results, newResult])
    setCustomTitle('')
    setCustomContent('')
    setIsAddingCustom(false)
  }, [results, customTitle, customContent, onChange])

  const selectedCount = results.filter((r) => r.selected).length

  if (!isEditMode) {
    // In Auto mode, just show results without editing capability
    return (
      <div className="space-y-2">
        {results.map((result) => (
          <div
            key={result.id}
            className="p-3 bg-slate-800/50 border border-slate-700 rounded-lg"
          >
            <h4 className="text-sm font-medium text-white truncate mb-1">
              {result.title}
            </h4>
            <p className="text-xs text-slate-400 line-clamp-2">
              {result.content}
            </p>
            {result.source && (
              <p className="text-xs text-slate-500 mt-1">Source: {result.source}</p>
            )}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Header with selection info */}
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>
          Selected {selectedCount} of {results.length} results
        </span>
        <button
          onClick={() =>
            onChange(results.map((r) => ({ ...r, selected: true })))
          }
          className="text-primary hover:underline"
        >
          Select All
        </button>
      </div>

      {/* Result cards */}
      <div className="space-y-2">
        {results.map((result) => (
          <EditableResultCard
            key={result.id}
            result={result}
            onToggleSelect={handleToggleSelect}
            onDelete={handleDelete}
            onEdit={handleEdit}
          />
        ))}
      </div>

      {/* Add custom content */}
      {isAddingCustom ? (
        <div className="p-3 bg-slate-800/50 border border-dashed border-primary/40 rounded-lg">
          <input
            type="text"
            value={customTitle}
            onChange={(e) => setCustomTitle(e.target.value)}
            placeholder="Title..."
            className="w-full p-2 mb-2 bg-slate-900 border border-slate-600 rounded-lg text-sm text-white focus:border-primary focus:outline-none"
          />
          <textarea
            value={customContent}
            onChange={(e) => setCustomContent(e.target.value)}
            placeholder="Content..."
            className="w-full p-2 bg-slate-900 border border-slate-600 rounded-lg text-sm text-white resize-none focus:border-primary focus:outline-none"
            rows={3}
          />
          <div className="flex justify-end gap-2 mt-2">
            <button
              onClick={() => {
                setIsAddingCustom(false)
                setCustomTitle('')
                setCustomContent('')
              }}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleAddCustom}
              disabled={!customTitle.trim() || !customContent.trim()}
              className="px-3 py-1.5 text-xs font-medium text-white bg-primary hover:bg-primary/80 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Add Content
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setIsAddingCustom(true)}
          className="w-full p-3 border border-dashed border-slate-700 rounded-lg text-sm text-slate-400 hover:text-primary hover:border-primary/40 transition-colors flex items-center justify-center gap-2"
        >
          <span className="material-symbols-outlined text-base">add</span>
          Add Custom Content
        </button>
      )}

      {/* Confirm button */}
      {onConfirm && (
        <div className="pt-2">
          <button
            onClick={onConfirm}
            className="w-full py-2.5 text-sm font-medium text-white bg-primary hover:bg-primary/80 rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined text-base">check</span>
            Confirm and Continue ({selectedCount} selected)
          </button>
        </div>
      )}
    </div>
  )
}

export default EditableResultList
