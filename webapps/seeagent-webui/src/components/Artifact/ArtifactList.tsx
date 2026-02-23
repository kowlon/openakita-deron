import type { Artifact } from '@/types/artifact'
import { ArtifactCard } from './ArtifactCard'

type ArtifactListProps = {
  artifacts: Artifact[]
  onDownload?: (artifact: Artifact) => void
}

export function ArtifactList({ artifacts, onDownload }: ArtifactListProps) {
  if (artifacts.length === 0) {
    return null
  }

  return (
    <div className="mt-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="material-symbols-outlined text-primary text-lg">folder_open</span>
        <h3 className="text-sm font-semibold text-primary">生成的文件</h3>
        <span className="text-xs text-slate-500">({artifacts.length})</span>
      </div>

      {/* Artifact Cards */}
      <div className="space-y-2">
        {artifacts.map((artifact) => (
          <ArtifactCard
            key={artifact.id}
            artifact={artifact}
            onDownload={onDownload}
          />
        ))}
      </div>
    </div>
  )
}

export default ArtifactList
