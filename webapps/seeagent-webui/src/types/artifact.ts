export type ArtifactType = 'pdf' | 'word' | 'excel' | 'image' | 'code' | 'text' | 'other'

export interface Artifact {
  id: string
  type: ArtifactType
  filename: string
  filepath: string
  size?: number  // in bytes
  downloadUrl?: string
  createdAt: number
  description?: string
}

/**
 * Get artifact type from file extension
 */
export function getArtifactType(filename: string): ArtifactType {
  const ext = filename.split('.').pop()?.toLowerCase() || ''

  const typeMap: Record<string, ArtifactType> = {
    // PDF
    'pdf': 'pdf',
    // Word
    'doc': 'word',
    'docx': 'word',
    // Excel
    'xls': 'excel',
    'xlsx': 'excel',
    'csv': 'excel',
    // Images
    'jpg': 'image',
    'jpeg': 'image',
    'png': 'image',
    'gif': 'image',
    'svg': 'image',
    'webp': 'image',
    // Code
    'js': 'code',
    'ts': 'code',
    'jsx': 'code',
    'tsx': 'code',
    'py': 'code',
    'java': 'code',
    'cpp': 'code',
    'c': 'code',
    'go': 'code',
    'rs': 'code',
    'html': 'code',
    'css': 'code',
    'json': 'code',
    'xml': 'code',
    'yaml': 'code',
    'yml': 'code',
    'md': 'code',
    // Text
    'txt': 'text',
    'log': 'text',
  }

  return typeMap[ext] || 'other'
}

/**
 * Format file size to human readable string
 */
export function formatFileSize(bytes?: number): string {
  if (!bytes) return ''

  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`
}

/**
 * Get icon name for artifact type
 */
export function getArtifactIcon(type: ArtifactType): string {
  const iconMap: Record<ArtifactType, string> = {
    'pdf': 'picture_as_pdf',
    'word': 'description',
    'excel': 'table_chart',
    'image': 'image',
    'code': 'code',
    'text': 'article',
    'other': 'insert_drive_file',
  }

  return iconMap[type]
}
