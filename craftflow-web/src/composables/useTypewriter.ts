import { ref } from 'vue'

/**
 * 打字机效果 Composable
 *
 * 恒定速率输出：每次 tick 输出固定数量的字符，保证视觉上的平滑。
 * 无论网络层如何批量送达数据，前端都以稳定速率渲染。
 *
 * 提取自 useChat.ts，供 Chat 和 TaskDetail 等多处复用。
 */
export function useTypewriter() {
  const content = ref('')
  const isStreaming = ref(false)

  let charBuffer = ''
  let streamDone = false
  let flushing = false
  let flushTimer: ReturnType<typeof setTimeout> | null = null

  /** 清理所有内部状态（不重置 content） */
  function cleanup(): void {
    if (flushTimer) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
    charBuffer = ''
    flushing = false
    streamDone = false
    isStreaming.value = false
  }

  /** 重置所有状态（包括 content） */
  function reset(): void {
    cleanup()
    content.value = ''
  }

  /** 流结束时的收尾处理 */
  function finalize(): void {
    cleanup()
  }

  /**
   * 恒定速率输出：每次 tick 输出固定数量的字符。
   * 30ms 间隔，每 tick 2 字符 ≈ 67 字符/秒。
   * 积压超过 60 字符时加速到每 tick 4 字符。
   */
  function scheduleFlush(): void {
    if (flushTimer) {
      clearTimeout(flushTimer)
    }

    flushTimer = setTimeout(() => {
      if (charBuffer.length > 0) {
        const n = charBuffer.length > 60 ? 4 : 2
        content.value += charBuffer.slice(0, n)
        charBuffer = charBuffer.slice(n)
      }

      if (streamDone && charBuffer.length === 0) {
        flushing = false
        finalize()
        return
      }

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

  /** 追加 token 到缓冲区并启动刷新 */
  function appendToken(token: string): void {
    if (!token) return
    charBuffer += token
    startFlush()
  }

  /** 标记流结束，等待缓冲区清空后自动 finalize */
  function finish(): void {
    streamDone = true
    if (charBuffer.length === 0 && !flushing) {
      finalize()
    }
  }

  /** 启动流式输出 */
  function start(): void {
    reset()
    isStreaming.value = true
  }

  /** 取消流式输出，保留已输出内容 */
  function cancel(): void {
    charBuffer = ''
    flushing = false
    streamDone = true
    finalize()
  }

  return {
    content,
    isStreaming,
    start,
    appendToken,
    finish,
    cancel,
    reset,
  }
}
