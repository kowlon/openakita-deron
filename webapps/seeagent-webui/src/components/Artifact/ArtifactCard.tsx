import type { Artifact } from '@/types/artifact'
import { getArtifactType, formatFileSize, getArtifactIcon } from '@/types/artifact'

type ArtifactCardProps = {
  artifact: Artifact
  onDownload?: (artifact: Artifact) => void
  onPreview?: (artifact: Artifact) => void
}

export function ArtifactCard({ artifact, onDownload, onPreview }: ArtifactCardProps) {
  const artifactType = artifact.type || getArtifactType(artifact.filename)
  const iconName = getArtifactIcon(artifactType)
  const fileSize = formatFileSize(artifact.size)

  // Check if file can be previewed
  const canPreview = artifactType === 'pdf' || artifactType === 'image'

  const handleDownload = () => {
    if (artifact.downloadUrl) {
      // Create a temporary link and trigger download
      const link = document.createElement('a')
      link.href = artifact.downloadUrl
      link.download = artifact.filename
      link.target = '_blank'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } else if (onDownload) {
      onDownload(artifact)
    }
  }

  const handlePreview = () => {
    if (onPreview) {
      onPreview(artifact)
    } else if (artifact.downloadUrl || artifact.filepath) {
      // Open in new window/tab for preview
      const previewUrl = artifact.downloadUrl || `/api/files/preview?path=${encodeURIComponent(artifact.filepath)}`
      window.open(previewUrl, '_blank')
    }
  }

  // Get color based on type
  const getTypeColor = (type: string): string => {
    const colors: Record<string, string> = {
      'pdf': 'text-red-400',
      'word': 'text-blue-400',
      'excel': 'text-green-400',
      'image': 'text-purple-400',
      'code': 'text-yellow-400',
      'text': 'text-slate-400',
      'other': 'text-slate-400',
    }
    return colors[type] || colors['other']
  }

  return (
    <div className="flex items-center gap-3 p-3 bg-slate-800/50 border border-slate-700 rounded-lg hover:border-primary/40 transition-colors group">
      {/* File Icon */}
      <div className={`p-2 rounded-lg bg-slate-900/50 ${getTypeColor(artifactType)}`}>
        <span className="material-symbols-outlined text-2xl">{iconName}</span>
      </div>

      {/* File Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate" title={artifact.filename}>
          {artifact.filename}
        </p>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="uppercase">{artifactType}</span>
          {fileSize && (
            <>
              <span>•</span>
              <span>{fileSize}</span>
            </>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-1">
        {/* Preview Button - only for PDF and images */}
        {canPreview && (
          <button
            onClick={handlePreview}
            className="p-2 text-slate-500 hover:text-primary hover:bg-primary/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
            title="Preview file"
          >
            <span className="material-symbols-outlined text-xl">visibility</span>
          </button>
        )}

        {/* Download Button */}
        <button
          onClick={handleDownload}
          className="p-2 text-slate-500 hover:text-primary hover:bg-primary/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
          title="Download file"
        >
          <span className="material-symbols-outlined text-xl">download</span>
        </button>
      </div>
    </div>
  )
}

export default ArtifactCard
