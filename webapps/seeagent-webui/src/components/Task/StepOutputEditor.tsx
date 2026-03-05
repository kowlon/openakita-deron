import { FC, useState } from 'react'
import type { TaskStep } from '../../types/task'

interface StepOutputEditorProps {
  step: TaskStep
  onSave?: (output: Record<string, unknown>) => void
  onConfirm?: () => void
  readOnly?: boolean
}

export const StepOutputEditor: FC<StepOutputEditorProps> = ({
  step,
  onSave,
  onConfirm,
  readOnly = false,
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [editedOutput, setEditedOutput] = useState<string>(
    JSON.stringify(step.output || {}, null, 2)
  )
  const [error, setError] = useState<string | null>(null)

  const handleSave = () => {
    try {
      const parsed = JSON.parse(editedOutput)
      setError(null)
      onSave?.(parsed)
      setIsEditing(false)
    } catch {
      setError('Invalid JSON format')
    }
  }

  const handleCancel = () => {
    setEditedOutput(JSON.stringify(step.output || {}, null, 2))
    setError(null)
    setIsEditing(false)
  }

  if (!step.output && !isEditing) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 text-center">
        <p className="text-gray-500 text-sm">No output available</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-900">{step.name}</h4>
          {step.description && (
            <p className="text-xs text-gray-500 mt-0.5">{step.description}</p>
          )}
        </div>
        {!readOnly && !isEditing && (
          <button
            onClick={() => setIsEditing(true)}
            className="px-2 py-1 text-gray-600 text-xs hover:text-gray-900 transition-colors"
          >
            Edit
          </button>
        )}
      </div>

      {/* Output Content */}
      <div className="p-4">
        {isEditing ? (
          <div>
            <textarea
              value={editedOutput}
              onChange={(e) => setEditedOutput(e.target.value)}
              className="w-full h-48 font-mono text-sm border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="JSON output..."
            />
            {error && (
              <p className="text-red-500 text-xs mt-1">{error}</p>
            )}
            <div className="flex justify-end gap-2 mt-3">
              <button
                onClick={handleCancel}
                className="px-3 py-1.5 text-gray-600 text-sm rounded-md hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-3 py-1.5 bg-blue-500 text-white text-sm rounded-md hover:bg-blue-600 transition-colors"
              >
                Save
              </button>
            </div>
          </div>
        ) : (
          <pre className="bg-gray-50 rounded-md p-3 overflow-auto text-sm font-mono text-gray-700">
            {JSON.stringify(step.output, null, 2)}
          </pre>
        )}
      </div>

      {/* Confirmation Actions */}
      {step.requires_confirmation && !isEditing && (
        <div className="px-4 py-3 bg-yellow-50 border-t border-yellow-100 flex items-center justify-between">
          <span className="text-xs text-yellow-700">
            This step requires confirmation before proceeding
          </span>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 bg-yellow-500 text-white text-sm rounded-md hover:bg-yellow-600 transition-colors"
          >
            Confirm & Continue
          </button>
        </div>
      )}
    </div>
  )
}