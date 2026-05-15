/** 对话 API — SSE 流式通道 */

import type { ChatRequest, ChatChunk } from '@/api/types/chat'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

/** SSE 流式对话选项 */
export interface StreamChatOptions {
  /** 对话请求数据 */
  request: ChatRequest
  /** 收到 chunk 时的回调 */
  onChunk: (chunk: ChatChunk) => void
  /** 流结束时的回调 */
  onDone: () => void
  /** 出错时的回调 */
  onError: (error: Error) => void
  /** 用于取消请求的 AbortSignal */
  signal?: AbortSignal
}

/**
 * 发起 SSE 流式对话请求
 *
 * 使用 fetch + ReadableStream 逐块读取 SSE 数据。
 * 不使用 Axios，因为 SSE 需要流式读取响应体。
 */
export async function streamChat(options: StreamChatOptions): Promise<void> {
  const { request, onChunk, onDone, onError, signal } = options

  try {
    const response = await fetch(`${BASE_URL}/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    })

    if (!response.ok) {
      const errorBody = await response.text()
      let errorMessage = `HTTP ${response.status}`
      try {
        const parsed = JSON.parse(errorBody) as Record<string, unknown>
        // 优先使用 message 字段（用户友好），其次 detail，最后 error
        errorMessage =
          (parsed.message as string) ??
          (parsed.detail as string) ??
          (parsed.error as string) ??
          errorMessage
      } catch {
        // errorBody 非 JSON，使用原始文本
        errorMessage = errorBody || errorMessage
      }
      onError(new Error(errorMessage))
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError(new Error('无法读取响应流'))
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      // 保留最后一行（可能不完整）
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6)
        if (data === '[DONE]') {
          onDone()
          return
        }

        try {
          const chunk = JSON.parse(data) as ChatChunk
          onChunk(chunk)
          if (chunk.done) {
            onDone()
            return
          }
        } catch {
          // 忽略无法解析的行
        }
      }
    }

    // 流正常结束但未收到 [DONE]
    onDone()
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      // 用户主动取消，不报错
      onDone()
      return
    }
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}
