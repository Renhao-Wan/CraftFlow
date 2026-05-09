/**
 * WebSocket Vue Composable
 *
 * 包装 wsClient，提供 Vue 响应式接口：
 * - isConnected / isReconnecting 响应式状态
 * - sendAndWait<T> 类型安全的请求-响应
 * - onMessage 自动清理的监听注册
 * - 组件卸载时自动清理
 */

import { computed, onUnmounted, type Ref } from 'vue'
import {
  wsClient,
  type WsMessage,
  type ServerMessageType,
  type ClientMessageType,
} from '@/api/wsClient'

/** useWebSocket 返回值 */
export interface UseWebSocketReturn {
  /** WebSocket 是否已连接 */
  isConnected: Ref<boolean>
  /** 是否正在重连 */
  isReconnecting: Ref<boolean>
  /** 重连次数 */
  reconnectAttempts: Ref<number>
  /** 手动连接 */
  connect: () => void
  /** 手动断开 */
  disconnect: () => void
  /** 发送消息（不等待响应） */
  send: (type: ClientMessageType, payload?: Record<string, unknown>) => boolean
  /** 发送消息并等待匹配的响应 */
  sendAndWait: <T = WsMessage>(
    type: ClientMessageType,
    payload?: Record<string, unknown>,
    timeoutMs?: number,
  ) => Promise<T>
  /** 注册消息监听，组件卸载时自动清理 */
  onMessage: (type: ServerMessageType, handler: (message: WsMessage) => void) => void
}

/**
 * WebSocket Composable
 *
 * @example
 * ```vue
 * <script setup lang="ts">
 * const { isConnected, sendAndWait, onMessage } = useWebSocket()
 *
 * onMessage('task_update', (msg) => {
 *   console.log('任务更新:', msg)
 * })
 *
 * async function createTask() {
 *   const response = await sendAndWait('create_creation', { topic: '主题' })
 *   // response 类型为 WsMessage
 * }
 * </script>
 * ```
 */
export function useWebSocket(): UseWebSocketReturn {
  // 当前组件注册的监听器，卸载时批量清理
  const registeredHandlers = new Map<ServerMessageType, Set<(message: WsMessage) => void>>()

  function onMessage(type: ServerMessageType, handler: (message: WsMessage) => void): void {
    wsClient.on(type, handler)

    if (!registeredHandlers.has(type)) {
      registeredHandlers.set(type, new Set())
    }
    registeredHandlers.get(type)!.add(handler)
  }

  function send(
    type: ClientMessageType,
    payload: Record<string, unknown> = {},
  ): boolean {
    return wsClient.send({ type, ...payload })
  }

  async function sendAndWait<T = WsMessage>(
    type: ClientMessageType,
    payload: Record<string, unknown> = {},
    timeoutMs = 30_000,
  ): Promise<T> {
    const message = await wsClient.sendAndWait(type, payload, timeoutMs)
    return message as T
  }

  // 组件卸载时清理本组件注册的所有监听器
  onUnmounted(() => {
    for (const [type, handlerSet] of registeredHandlers) {
      for (const handler of handlerSet) {
        wsClient.off(type, handler)
      }
    }
    registeredHandlers.clear()
  })

  return {
    isConnected: computed(() => wsClient.isConnected.value),
    isReconnecting: computed(() => wsClient.isReconnecting.value),
    reconnectAttempts: computed(() => wsClient.reconnectAttempts.value),
    connect: wsClient.connect,
    disconnect: wsClient.disconnect,
    send,
    sendAndWait,
    onMessage,
  }
}
