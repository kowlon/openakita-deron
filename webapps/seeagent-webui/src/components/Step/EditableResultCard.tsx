import { useState } from 'react'

export interface EditableResult {
  id: string
  title: string
  content: string
  source?: string
  selected: boolean
}

type EditableResultCardProps = {
  result: EditableResult
  onToggleSelect: (id: string) => void
  onDelete: (id: string) => void
  onEdit: (id: string, updates: Partial<EditableResult>) => void
}

/**
 * Editable result card component for Edit mode
 * Supports checkbox selection, delete, and content editing
 */
export function EditableResultCard({
  result,
  onToggleSelect,
  onDelete,
  onEdit,
}: EditableResultCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState(result.content)

  const handleSaveEdit = () => {
    onEdit(result.id, { content: editContent })
    setIsEditing(false)
  }

  const handleCancelEdit = () => {
    setEditContent(result.content)
    setIsEditing(false)
  }

  return (
    <div
      className={`relative p-3 rounded-lg border transition-all ${
        result.selected
          ? 'bg-primary/10 border-primary/40'
          : 'bg-slate-800/50 border-slate-700'
      }`}
    >
      {/* Selection checkbox */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => onToggleSelect(result.id)}
          className={`mt-1 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors shrink-0 ${
            result.selected
              ? 'bg-primary border-primary text-white'
              : 'border-slate-500 hover:border-primary'
          }`}
        >
          {result.selected && (
            <span className="material-symbols-outlined text-sm">check</span>
          )}
        </button>

        {/* Content area */}
        <div className="flex-1 min-w-0">
          {/* Title */}
          <div className="flex items-center justify-between gap-2 mb-1">
            <h4
              className={`text-sm font-medium truncate ${
                result.selected ? 'text-white' : 'text-slate-400'
              }`}
              title={result.title}
            >
              {result.title}
            </h4>
            {/* Action buttons */}
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => setIsEditing(true)}
                className="p-1 text-slate-500 hover:text-primary hover:bg-primary/10 rounded transition-colors"
                title="Edit content"
              >
                <span className="material-symbols-outlined text-base">edit</span>
              </button>
              <button
                onClick={() => onDelete(result.id)}
                className="p-1 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded transition-colors"
                title="Delete result"
              >
                <span className="material-symbols-outlined text-base">delete</span>
              </button>
            </div>
          </div>

          {/* Content - display or edit mode */}
          {isEditing ? (
            <div className="mt-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full p-2 bg-slate-900 border border-slate-600 rounded-lg text-sm text-white resize-none focus:border-primary focus:outline-none"
                rows={4}
                autoFocus
              />
              <div className="flex justify-end gap-2 mt-2">
                <button
                  onClick={handleCancelEdit}
                  className="px-2 py-1 text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  className="px-3 py-1 text-xs font-medium text-white bg-primary hover:bg-primary/80 rounded-lg transition-colors"
                >
                  Save
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Content text */}
              <p
                className={`text-xs leading-relaxed line-clamp-3 ${
                  result.selected ? 'text-slate-300' : 'text-slate-500'
                }`}
                onClick={() => setIsEditing(true)}
                style={{ cursor: 'pointer' }}
              >
                {result.content}
              </p>

              {/* Source */}
              {result.source && (
                <p className="text-xs text-slate-500 mt-1">
                  Source: {result.source}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default EditableResultCard
