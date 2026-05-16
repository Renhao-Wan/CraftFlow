import { ref, watch } from 'vue'
import { streamChat } from '@/api/chat'
import { useTypewriter } from '@/composables/useTypewriter'
import type { ChatMessage, ChatChunk } from '@/api/types/chat'

/** 对话 Composable — 管理消息列表和流式控制 */
export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  let abortController: AbortController | null = null
  let assistantIndex = -1
  const typewriter = useTypewriter()

  // 同步打字机内容到 assistant 消息
  watch(
    () => typewriter.content.value,
    (newContent) => {
      if (assistantIndex >= 0 && assistantIndex < messages.value.length) {
        const target = messages.value[assistantIndex]
        if (target) {
          target.content = newContent
        }
      }
    },
  )

  // 打字机缓冲区刷完后收尾（onDone 时缓冲区可能还有积压）
  watch(
    () => typewriter.isStreaming.value,
    (val) => {
      if (!val && isStreaming.value) {
        finalize()
      }
    },
  )

  /** 移除空的 assistant 消息 */
  function removeEmptyAssistant(): void {
    messages.value = messages.value.filter(
      (m) => !(m.role === 'assistant' && !m.content),
    )
  }

  /** 清理所有状态 */
  function cleanup(): void {
    typewriter.reset()
    isStreaming.value = false
    abortController = null
    assistantIndex = -1
  }

  /** 流结束时的收尾处理 */
  function finalize(): void {
    removeEmptyAssistant()
    cleanup()
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
    typewriter.start()

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
          typewriter.appendToken(chunk.content)
        }
      },
      onDone: () => {
        typewriter.finish()
        // 如果缓冲区已空且没有在刷新，直接完成
        if (!typewriter.isStreaming.value) {
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
      typewriter.cancel()
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
