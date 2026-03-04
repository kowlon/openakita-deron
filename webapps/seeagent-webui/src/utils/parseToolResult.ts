/**
 * Parsed result item from tool output
 */
export interface ParsedResult {
  id: string
  title: string
  content: string
  source?: string
  selected?: boolean
}

/**
 * Parse tool result output into parsed result items
 * Supports web search, news search, and other structured outputs
 */

/**
 * Try to parse JSON array from tool output
 * Returns null if not valid JSON array
 */
function tryParseJsonArray(output: string): ParsedResult[] | null {
  try {
    // Try to extract JSON array from the output
    const trimmed = output.trim()

    // Direct JSON array
    if (trimmed.startsWith('[')) {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        return parsed.map((item, index) => ({
          id: item.id || `json-${Date.now()}-${index}`,
          title: item.title || `Result ${index + 1}`,
          content: item.content || item.description || item.body || '',
          source: item.source || item.url || '',
          selected: true,
        }))
      }
    }

    // Try to find JSON array in the output
    const jsonMatch = output.match(/\[[\s\S]*\]/)
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0])
      if (Array.isArray(parsed)) {
        return parsed.map((item, index) => ({
          id: item.id || `json-${Date.now()}-${index}`,
          title: item.title || `Result ${index + 1}`,
          content: item.content || item.description || item.body || '',
          source: item.source || item.url || '',
          selected: true,
        }))
      }
    }

    return null
  } catch {
    return null
  }
}

/**
 * Parse web search results from tool output
 * Handles various formats: JSON array, numbered list, markdown format
 */
export function parseWebSearchResults(output: string | undefined): ParsedResult[] {
  if (!output) return []

  const results: ParsedResult[] = []

  // Try to parse as numbered list format (common LLM output format)
  // Format: **1. Title**\nURL\nSnippet\n
  const numberedPattern = /\*\*(\d+)\.\s+([^*]+)\*\*\s*\n([^\n]+)\s*\n([^\n*(?=\*\*|$)]+)/g
  let match

  while ((match = numberedPattern.exec(output)) !== null) {
    const [, , title, url, snippet] = match
    if (title && snippet) {
      // Extract source from URL
      let source = ''
      try {
        const urlObj = new URL(url.trim())
        source = urlObj.hostname.replace('www.', '')
      } catch {
        source = 'Web'
      }

      results.push({
        id: `search-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        title: title.trim(),
        content: snippet.trim(),
        source,
        selected: true,
      })
    }
  }

  // If no results from numbered pattern, try simple line-by-line parsing
  if (results.length === 0) {
    const lines = output.split('\n').filter((line) => line.trim())

    let currentTitle = ''
    let currentContent = ''
    let currentSource = ''

    for (const line of lines) {
      const trimmedLine = line.trim()

      // Check if this is a title line (starts with ** or **N.)
      if (trimmedLine.startsWith('**') && trimmedLine.endsWith('**')) {
        // Save previous result if exists
        if (currentTitle && currentContent) {
          results.push({
            id: `search-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            title: currentTitle,
            content: currentContent,
            source: currentSource || 'Web',
            selected: true,
          })
        }

        // Extract title (remove ** markers and number)
        currentTitle = trimmedLine.replace(/\*\*/g, '').replace(/^\d+\.\s*/, '').trim()
        currentContent = ''
        currentSource = ''
      }
      // Check if this is a URL line
      else if (trimmedLine.startsWith('http://') || trimmedLine.startsWith('https://')) {
        try {
          const urlObj = new URL(trimmedLine)
          currentSource = urlObj.hostname.replace('www.', '')
        } catch {
          // Not a valid URL, might be content
          if (currentContent) {
            currentContent += ' ' + trimmedLine
          } else {
            currentContent = trimmedLine
          }
        }
      }
      // Otherwise it's content
      else if (trimmedLine && !trimmedLine.startsWith('Source:')) {
        if (currentContent) {
          currentContent += ' ' + trimmedLine
        } else {
          currentContent = trimmedLine
        }
      }
    }

    // Save the last result
    if (currentTitle && currentContent) {
      results.push({
        id: `search-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        title: currentTitle,
        content: currentContent,
        source: currentSource || 'Web',
        selected: true,
      })
    }
  }

  // If still no results, create a single result from the whole output
  if (results.length === 0 && output.trim()) {
    results.push({
      id: `search-${Date.now()}`,
      title: 'Search Result',
      content: output.trim(),
      source: 'Web',
      selected: true,
    })
  }

  return results
}

/**
 * Parse news search results from tool output
 */
export function parseNewsSearchResults(output: string | undefined): ParsedResult[] {
  if (!output) return []

  // Similar to web search but also extracts date and source
  const results: ParsedResult[] = []

  // Pattern: **N. Title** (Source Date)\nURL\nSnippet
  const newsPattern = /\*\*(\d+)\.\s+([^*]+)\*\*\s*\(([^)]+)\)\s*\n([^\n]+)\s*\n([^\n]+)/g
  let match

  while ((match = newsPattern.exec(output)) !== null) {
    const [, , title, sourceInfo, , snippet] = match
    if (title && snippet) {
      results.push({
        id: `news-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        title: title.trim(),
        content: snippet.trim(),
        source: sourceInfo.trim() || 'News',
        selected: true,
      })
    }
  }

  // Fallback to web search parsing if news pattern doesn't match
  if (results.length === 0) {
    return parseWebSearchResults(output)
  }

  return results
}

/**
 * Parse generic tool output into parsed results
 */
export function parseGenericResults(output: string | undefined): ParsedResult[] {
  if (!output) return []

  // For generic output, create a single parsed result
  return [
    {
      id: `result-${Date.now()}`,
      title: 'Result',
      content: output.trim(),
      source: 'Tool Output',
      selected: true,
    },
  ]
}

/**
 * Main function to parse tool results based on tool name
 */
export function parseToolResults(
  toolName: string,
  output: string | undefined
): ParsedResult[] {
  if (!output) return []

  // First, try to parse as JSON array (for test-search and other JSON-returning tools)
  const jsonResults = tryParseJsonArray(output)
  if (jsonResults && jsonResults.length > 0) {
    return jsonResults
  }

  const toolNameLower = toolName.toLowerCase()

  if (toolNameLower.includes('web_search') || toolNameLower.includes('search')) {
    return parseWebSearchResults(output)
  }

  if (toolNameLower.includes('news_search') || toolNameLower.includes('news')) {
    return parseNewsSearchResults(output)
  }

  // Default to generic parsing
  return parseGenericResults(output)
}

export default parseToolResults
