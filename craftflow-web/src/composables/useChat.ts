import { ref } from 'vue'
import { streamChat } from '@/api/chat'
import type { ChatMessage, ChatChunk } from '@/api/types/chat'

/** 对话 Composable — 管理消息列表和流式控制 */
export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  let abortController: AbortController | null = null
  let assistantIndex = -1
  let charBuffer = ''
  let streamDone = false
  let flushing = false
  let flushTimer: ReturnType<typeof setTimeout> | null = null

  /** 清理所有状态 */
  function cleanup(): void {
    if (flushTimer) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
    charBuffer = ''
    flushing = false
    streamDone = false
    isStreaming.value = false
    abortController = null
    assistantIndex = -1
  }

  /** 移除空的 assistant 消息 */
  function removeEmptyAssistant(): void {
    messages.value = messages.value.filter(
      (m) => !(m.role === 'assistant' && !m.content),
    )
  }

  /** 流结束时的收尾处理 */
  function finalize(): void {
    removeEmptyAssistant()
    cleanup()
  }

  /**
   * 恒定速率输出：每次 tick 输出固定数量的字符，保证视觉上的平滑。
   * 无论网络层如何批量送达数据，前端都以稳定速率渲染。
   */
  function scheduleFlush(): void {
    if (flushTimer) {
      clearTimeout(flushTimer)
    }

    flushTimer = setTimeout(() => {
      if (charBuffer.length > 0 && assistantIndex >= 0) {
        // 恒定速率：每 tick 输出 2 个字符，30ms 间隔 ≈ 67 字符/秒
        // 积压过多时加速追赶到每 tick 4 个字符
        const n = charBuffer.length > 60 ? 4 : 2
        const target = messages.value[assistantIndex]
        if (target) {
          target.content += charBuffer.slice(0, n)
        }
        charBuffer = charBuffer.slice(n)
      }

      if (streamDone && charBuffer.length === 0) {
        flushing = false
        finalize()
        return
      }

      // 继续下一轮
      if (isStreaming.value) {
        scheduleFlush()
      }
    }, 30)
  }

  function startFlush(): void {
    if (flushing) return
    flushing = true
    scheduleFlush()
  }

  async function send(content: string, profileId?: string): Promise<void> {
    if (!content.trim() || isStreaming.value) return

    const userMessage: ChatMessage = { role: 'user', content: content.trim() }
    const assistantMessage: ChatMessage = { role: 'assistant', content: '' }
    messages.value.push(userMessage, assistantMessage)
    assistantIndex = messages.value.length - 1

    isStreaming.value = true
    error.value = null
    abortController = new AbortController()
    charBuffer = ''
    streamDone = false
    flushing = false

    const requestMessages = messages.value.slice(0, -1)

    await streamChat({
      request: {
        messages: requestMessages,
        profile_id: profileId,
      },
      onChunk: (chunk: ChatChunk) => {
        if (chunk.error) {
          error.value = chunk.error
          return
        }
        if (chunk.content) {
          charBuffer += chunk.content
          startFlush()
        }
      },
      onDone: () => {
        streamDone = true
        // 如果缓冲区已空且没有在刷新，直接完成
        if (charBuffer.length === 0 && !flushing) {
          finalize()
        }
      },
      onError: (err: Error) => {
        error.value = err.message
        removeEmptyAssistant()
        cleanup()
      },
      signal: abortController.signal,
    })
  }

  /** 取消当前流式输出，保留已输出的内容 */
  function cancel(): void {
    if (abortController) {
      abortController.abort()
      // 清空缓冲区，不保留未显示的内容
      charBuffer = ''
      flushing = false
      streamDone = true
      finalize()
    }
  }

  function clear(): void {
    cancel()
    messages.value = []
    error.value = null
  }

  return { messages, isStreaming, error, send, cancel, clear }
}
