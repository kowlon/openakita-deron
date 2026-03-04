const API_BASE = '/api'

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export async function apiPostStream(
  path: string,
  body: unknown,
  onEvent: (event: Record<string, unknown>) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const error = new Error(`API Error: ${response.status} ${response.statusText}`)
    onError?.(error)
    throw error
  }

  const reader = response.body?.getReader()
  if (!reader) {
    const error = new Error('No response body')
    onError?.(error)
    throw error
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()
          console.log('[apiPostStream] Raw SSE data:', data)
          if (data === '[DONE]') {
            console.log('[apiPostStream] Received [DONE], completing stream')
            onComplete?.()
            return
          }
          try {
            const event = JSON.parse(data)
            console.log('[apiPostStream] Parsed event:', event)
            onEvent(event)
            if ((event as { type?: string }).type === 'done') {
              onComplete?.()
              await reader.cancel()
              return
            }
          } catch (e) {
            console.error('[apiPostStream] Parse error:', e, 'data:', data)
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  onComplete?.()
}
