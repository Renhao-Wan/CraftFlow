import { ref } from 'vue'
import { streamChat } from '@/api/chat'
import type { ChatMessage, ChatChunk } from '@/api/types/chat'

/** 对话 Composable — 管理消息列表和流式控制 */
export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  let abortController: AbortController | null = null

  /**
   * 发送消息并流式接收回复
   * @param content 用户输入内容
   * @param profileId 可选 LLM Profile ID
   */
  async function send(content: string, profileId?: string): Promise<void> {
    if (!content.trim() || isStreaming.value) return

    // 添加用户消息
    const userMessage: ChatMessage = { role: 'user', content: content.trim() }
    messages.value.push(userMessage)

    // 添加空的 assistant 消息（流式填充）
    const assistantMessage: ChatMessage = { role: 'assistant', content: '' }
    messages.value.push(assistantMessage)

    isStreaming.value = true
    error.value = null
    abortController = new AbortController()

    let hasError = false

    const requestMessages = messages.value.slice(0, -1) // 不包含空的 assistant 消息

    await streamChat({
      request: {
        messages: requestMessages,
        profile_id: profileId,
      },
      onChunk: (chunk: ChatChunk) => {
        if (chunk.error) {
          error.value = chunk.error
          hasError = true
          return
        }
        assistantMessage.content += chunk.content
      },
      onDone: () => {
        // 如果有错误或 assistant 消息为空，移除它
        if (hasError || !assistantMessage.content) {
          messages.value = messages.value.filter((m) => m !== assistantMessage)
        }
        // 清理所有残留的空 assistant 消息
        messages.value = messages.value.filter(
          (m) => !(m.role === 'assistant' && !m.content),
        )
        isStreaming.value = false
        abortController = null
      },
      onError: (err: Error) => {
        error.value = err.message
        // 移除当前 assistant 消息
        messages.value = messages.value.filter((m) => m !== assistantMessage)
        // 清理所有残留的空 assistant 消息
        messages.value = messages.value.filter(
          (m) => !(m.role === 'assistant' && !m.content),
        )
        isStreaming.value = false
        abortController = null
      },
      signal: abortController.signal,
    })
  }

  /** 取消当前流式生成 */
  function cancel(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
      isStreaming.value = false
    }
  }

  /** 清空对话历史 */
  function clear(): void {
    cancel()
    messages.value = []
    error.value = null
  }

  return { messages, isStreaming, error, send, cancel, clear }
}
