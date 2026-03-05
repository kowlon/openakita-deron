import { FC, useState, useMemo } from 'react'
import type { TaskStep } from '../../types/task'

interface StepOutputEditorProps {
  step: TaskStep
  onSave?: (output: Record<string, unknown>) => void
  onConfirm?: () => void
  readOnly?: boolean
}

/**
 * Simple markdown-like renderer for step output
 * Supports headers, lists, code blocks, and basic formatting
 */
function renderMarkdown(text: string): JSX.Element {
  const lines = text.split('\n')
  const elements: JSX.Element[] = []
  let inCodeBlock = false
  let codeContent = ''

  lines.forEach((line, idx) => {
    // Code block start/end
    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true
        codeContent = ''
      } else {
        inCodeBlock = false
        elements.push(
          <pre key={idx} className="bg-slate-800 text-slate-200 rounded-md p-3 overflow-auto text-sm font-mono my-2">
            <code>{codeContent}</code>
          </pre>
        )
      }
      return
    }

    if (inCodeBlock) {
      codeContent += (codeContent ? '\n' : '') + line
      return
    }

    // Headers
    if (line.startsWith('### ')) {
      elements.push(<h4 key={idx} className="text-sm font-semibold text-slate-800 mt-3 mb-1">{line.slice(4)}</h4>)
      return
    }
    if (line.startsWith('## ')) {
      elements.push(<h3 key={idx} className="text-base font-semibold text-slate-800 mt-4 mb-2">{line.slice(3)}</h3>)
      return
    }
    if (line.startsWith('# ')) {
      elements.push(<h2 key={idx} className="text-lg font-bold text-slate-900 mt-4 mb-2">{line.slice(2)}</h2>)
      return
    }

    // List items
    if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(<li key={idx} className="text-sm text-slate-700 ml-4">{renderInlineFormat(line.slice(2))}</li>)
      return
    }

    // Numbered list
    const numMatch = line.match(/^(\d+)\.\s+(.*)/)
    if (numMatch) {
      elements.push(
        <li key={idx} className="text-sm text-slate-700 ml-4 list-decimal">
          {renderInlineFormat(numMatch[2])}
        </li>
      )
      return
    }

    // Empty line
    if (!line.trim()) {
      elements.push(<div key={idx} className="h-2" />)
      return
    }

    // Regular paragraph
    elements.push(<p key={idx} className="text-sm text-slate-700 leading-relaxed">{renderInlineFormat(line)}</p>)
  })

  return <>{elements}</>
}

/**
 * Render inline formatting (bold, italic, code)
 */
function renderInlineFormat(text: string): JSX.Element {
  // Simple inline code
  const parts = text.split(/`([^`]+)`/)
  return (
    <>
      {parts.map((part, i) => (
        i % 2 === 1
          ? <code key={i} className="bg-slate-100 text-slate-800 px-1 py-0.5 rounded text-xs font-mono">{part}</code>
          : <span key={i}>{part}</span>
      ))}
    </>
  )
}

/**
 * Detect if output is markdown-like content
 */
function isMarkdownContent(content: unknown): boolean {
  if (typeof content !== 'string') return false
  // Check for common markdown patterns
  const mdPatterns = [
    /^#{1,6}\s/m,           // Headers
    /```/m,                  // Code blocks
    /^[-*]\s/m,             // Lists
    /^\d+\.\s/m,            // Numbered lists
    /\*\*[^*]+\*\*/,        // Bold
    /`[^`]+`/,              // Inline code
  ]
  return mdPatterns.some(p => p.test(content))
}

/**
 * Extract display content from step output
 */
function extractDisplayContent(output: Record<string, unknown> | undefined): { text: string; isMarkdown: boolean } {
  if (!output) return { text: '', isMarkdown: false }

  // Check for raw_output field (from SubAgent)
  if (output.raw_output && typeof output.raw_output === 'string') {
    return { text: output.raw_output, isMarkdown: isMarkdownContent(output.raw_output) }
  }

  // Check for output field
  if (output.output && typeof output.output === 'string') {
    return { text: output.output, isMarkdown: isMarkdownContent(output.output) }
  }

  // Check if output itself is a string
  if (typeof output === 'string') {
    return { text: output, isMarkdown: isMarkdownContent(output) }
  }

  // Fall back to JSON
  return { text: JSON.stringify(output, null, 2), isMarkdown: false }
}

export const StepOutputEditor: FC<StepOutputEditorProps> = ({
  step,
  onSave,
  onConfirm,
  readOnly = false,
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [viewMode, setViewMode] = useState<'preview' | 'raw'>('preview')

  const { text: displayText, isMarkdown } = useMemo(
    () => extractDisplayContent(step.output),
    [step.output]
  )

  const [editedOutput, setEditedOutput] = useState<string>(displayText)
  const [error, setError] = useState<string | null>(null)

  const handleSave = () => {
    try {
      // Try to parse as JSON first
      try {
        const parsed = JSON.parse(editedOutput)
        setError(null)
        onSave?.(parsed)
      } catch {
        // If not valid JSON, save as raw output
        setError(null)
        onSave?.({ raw_output: editedOutput })
      }
      setIsEditing(false)
    } catch (e) {
      setError('Failed to save output')
    }
  }

  const handleCancel = () => {
    setEditedOutput(displayText)
    setError(null)
    setIsEditing(false)
  }

  if (!step.output && !isEditing) {
    return (
      <div className="bg-slate-50 rounded-lg p-4 text-center border border-slate-200">
        <span className="material-symbols-outlined text-slate-400 text-2xl mb-2">description</span>
        <p className="text-slate-500 text-sm">No output available</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-sm">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-lg">output</span>
          <div>
            <h4 className="text-sm font-medium text-slate-900">{step.name}</h4>
            {step.description && (
              <p className="text-xs text-slate-500 mt-0.5">{step.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!readOnly && !isEditing && (
            <>
              {isMarkdown && (
                <div className="flex rounded-md overflow-hidden border border-slate-300">
                  <button
                    onClick={() => setViewMode('preview')}
                    className={`px-2 py-1 text-xs ${viewMode === 'preview' ? 'bg-primary text-white' : 'bg-white text-slate-600'}`}
                  >
                    Preview
                  </button>
                  <button
                    onClick={() => setViewMode('raw')}
                    className={`px-2 py-1 text-xs ${viewMode === 'raw' ? 'bg-primary text-white' : 'bg-white text-slate-600'}`}
                  >
                    Raw
                  </button>
                </div>
              )}
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-1 px-2 py-1 text-slate-600 text-xs hover:text-primary transition-colors"
              >
                <span className="material-symbols-outlined text-sm">edit</span>
                Edit
              </button>
            </>
          )}
        </div>
      </div>

      {/* Output Content */}
      <div className="p-4 max-h-96 overflow-auto">
        {isEditing ? (
          <div>
            <textarea
              value={editedOutput}
              onChange={(e) => setEditedOutput(e.target.value)}
              className="w-full h-64 font-mono text-sm border border-slate-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent bg-slate-50"
              placeholder="Edit output content..."
            />
            {error && (
              <p className="text-red-500 text-xs mt-1">{error}</p>
            )}
            <div className="flex justify-end gap-2 mt-3">
              <button
                onClick={handleCancel}
                className="px-3 py-1.5 text-slate-600 text-sm rounded-md hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-3 py-1.5 bg-primary text-white text-sm rounded-md hover:bg-primary/90 transition-colors"
              >
                Save
              </button>
            </div>
          </div>
        ) : (
          <>
            {isMarkdown && viewMode === 'preview' ? (
              <div className="prose prose-sm max-w-none">
                {renderMarkdown(displayText)}
              </div>
            ) : (
              <pre className="bg-slate-50 rounded-md p-3 overflow-auto text-sm font-mono text-slate-700 whitespace-pre-wrap">
                {displayText}
              </pre>
            )}
          </>
        )}
      </div>

      {/* Confirmation Actions */}
      {step.requires_confirmation && !isEditing && (
        <div className="px-4 py-3 bg-amber-50 border-t border-amber-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-amber-600 text-lg">warning</span>
            <span className="text-xs text-amber-700">
              This step requires confirmation before proceeding
            </span>
          </div>
          <button
            onClick={onConfirm}
            className="flex items-center gap-1 px-3 py-1.5 bg-amber-500 text-white text-sm rounded-md hover:bg-amber-600 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">check</span>
            Confirm & Continue
          </button>
        </div>
      )}
    </div>
  )
}