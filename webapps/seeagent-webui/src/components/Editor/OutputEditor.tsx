import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'

interface OutputEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
}

export function OutputEditor({ value, onChange, readOnly = false }: OutputEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value)

  // Sync editValue when value prop changes
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value)
    }
  }, [value, isEditing])

  const handleEdit = () => {
    if (!readOnly) {
      setIsEditing(true)
      setEditValue(value)
    }
  }

  const handleSave = () => {
    onChange(editValue)
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditValue(value)
    setIsEditing(false)
  }

  return (
    <div className="output-editor h-full flex flex-col bg-background-dark rounded-xl border border-primary/10">
      {/* Header */}
      <header className="flex items-center justify-between p-4 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-lg">output</span>
          <span className="text-sm font-medium text-white">Output Results</span>
        </div>
        <div className="flex items-center gap-2">
          {!readOnly && !isEditing && (
            <button
              onClick={handleEdit}
              className="flex items-center gap-1 px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
            >
              <span className="material-symbols-outlined text-sm">edit</span>
              Edit
            </button>
          )}
          {isEditing && (
            <>
              <button
                onClick={handleCancel}
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
              >
                <span className="material-symbols-outlined text-sm">close</span>
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="flex items-center gap-1 px-3 py-1.5 text-xs bg-primary text-white rounded-lg hover:bg-primary/80 transition-colors"
              >
                <span className="material-symbols-outlined text-sm">save</span>
                Save
              </button>
            </>
          )}
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {isEditing ? (
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="w-full h-full bg-slate-900 border border-slate-700 rounded-lg p-4 font-mono text-sm text-slate-300 resize-none focus:outline-none focus:border-primary"
            placeholder="Enter output content (supports Markdown)..."
          />
        ) : (
          <div className="markdown-content prose prose-invert prose-sm max-w-none">
            {value ? (
              <ReactMarkdown
                components={{
                  // Custom styling for markdown elements
                  h1: ({ children }) => (
                    <h1 className="text-xl font-bold text-white mb-4 mt-0">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-lg font-bold text-white mb-3 mt-4">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base font-bold text-white mb-2 mt-3">{children}</h3>
                  ),
                  p: ({ children }) => (
                    <p className="text-sm text-slate-300 mb-2 leading-relaxed">{children}</p>
                  ),
                  code: ({ className, children, ...props }) => {
                    const isInline = !className
                    return isInline ? (
                      <code className="bg-slate-800 text-primary px-1.5 py-0.5 rounded text-xs" {...props}>
                        {children}
                      </code>
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    )
                  },
                  pre: ({ children }) => (
                    <pre className="bg-slate-900 rounded-lg p-3 overflow-auto text-xs mb-3">
                      {children}
                    </pre>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside text-sm text-slate-300 mb-2 space-y-1">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside text-sm text-slate-300 mb-2 space-y-1">
                      {children}
                    </ol>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-primary/50 pl-4 text-sm text-slate-400 italic mb-2">
                      {children}
                    </blockquote>
                  ),
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {value}
              </ReactMarkdown>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 py-8">
                <span className="material-symbols-outlined text-4xl mb-2">output</span>
                <p className="text-sm">No output available</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer with status */}
      <footer className="px-4 py-2 border-t border-slate-700 text-xs text-slate-500 flex justify-between">
        <span className="flex items-center gap-1">
          <span className="material-symbols-outlined text-sm">info</span>
          {isEditing ? 'Editing mode' : 'Markdown supported'}
        </span>
        {!readOnly && (
          <span className={isEditing ? 'text-primary' : ''}>
            {isEditing ? 'Unsaved changes' : 'Click Edit to modify'}
          </span>
        )}
      </footer>
    </div>
  )
}

export default OutputEditor