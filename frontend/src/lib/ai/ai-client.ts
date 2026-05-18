/**
 * SSE client for the in-app AI rail.
 *
 * The backend emits one JSON-encoded event per `data: ...` line, terminated
 * by a blank line. Event shapes (see src/finclaide/ai.py):
 *   { type: 'text_delta', delta: string }
 *   { type: 'tool_use', id, name, input }
 *   { type: 'tool_result', id, name, is_error, result }
 *   { type: 'done', stop_reason }
 *   { type: 'error', code, message }
 */

import { withBasePath } from '$lib/runtime'

export type AIChatEvent =
  | { type: 'text_delta'; delta: string }
  | { type: 'tool_use'; id: string; name: string; input: Record<string, unknown> }
  | {
      type: 'tool_result'
      id: string
      name: string
      is_error: boolean
      result: unknown
    }
  | { type: 'done'; stop_reason: string }
  | { type: 'error'; code?: string; message: string }

export type AIChatMessage = {
  role: 'user' | 'assistant'
  content: string | Array<Record<string, unknown>>
}

/**
 * Stream chat events from the AI rail.
 *
 * Throws an `AIUnavailableError` when the backend returns 503 — the caller
 * surfaces that to the rail header. Other HTTP failures bubble as standard
 * errors with the response status attached.
 */
export class AIUnavailableError extends Error {
  constructor() {
    super('AI rail unavailable — set ANTHROPIC_API_KEY')
    this.name = 'AIUnavailableError'
  }
}

export async function* streamChat(
  messages: AIChatMessage[],
  options: { month?: string; signal?: AbortSignal } = {},
): AsyncGenerator<AIChatEvent> {
  const response = await fetch(withBasePath('/ui-api/ai/chat'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Finclaide-UI': '1',
    },
    body: JSON.stringify({ messages, month: options.month ?? null }),
    signal: options.signal,
  })

  if (response.status === 503) throw new AIUnavailableError()
  if (!response.ok) {
    throw new Error(`AI request failed: ${response.status}`)
  }
  if (!response.body) {
    throw new Error('AI response had no body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const chunk = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        for (const line of chunk.split('\n')) {
          const trimmed = line.trimStart()
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.slice(5).trim()
          if (!payload) continue
          try {
            yield JSON.parse(payload) as AIChatEvent
          } catch (parseError) {
            // Skip malformed events — never fatal.
            console.warn('AI: dropped malformed SSE payload', parseError)
          }
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    try {
      await reader.cancel()
    } catch {
      // Closed by the server already.
    }
  }
}
