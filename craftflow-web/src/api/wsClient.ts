/**
 * WebSocket 客户端
 *
 * 单例 WebSocket 管理，支持：
 * - 指数退避自动重连（1s → 2s → 4s → 8s → 16s → 30s，最大 6 次）
 * - 心跳机制（30s ping，10s pong 超时）
 * - requestId 请求-响应配对
 * - 断连期间消息缓存，重连后自动发送
 * - 事件驱动的消息分发
 */

import { ref } from 'vue'

/** 服务端推送消息类型 */
export type ServerMessageType =
  | 'task_created'
  | 'task_update'
  | 'task_result'
  | 'task_error'
  | 'task_status'
  | 'error'
  | 'pong'

/** 客户端发送消息类型 */
export type ClientMessageType =
  | 'create_creation'
  | 'create_polishing'
  | 'resume_task'
  | 'get_task_status'
  | 'subscribe_task'
  | 'unsubscribe_task'
  | 'ping'

/** 通用服务端消息结构 */
export interface WsMessage {
  type: ServerMessageType
  requestId?: string
  taskId?: string
  [key: string]: unknown
}

/** 消息处理器 */
type MessageHandler = (message: WsMessage) => void

/** 待发送消息 */
interface PendingMessage {
  data: Record<string, unknown>
  timestamp: number
}

// ─── 常量 ──────────────────────────────────────────

const RECONNECT_DELAYS = [1_000, 2_000, 4_000, 8_000, 16_000, 30_000] as const
const MAX_RECONNECT_ATTEMPTS = RECONNECT_DELAYS.length
const HEARTBEAT_INTERVAL = 30_000
const PONG_TIMEOUT = 10_000
const MAX_PENDING_MESSAGES = 100
const PENDING_MESSAGE_TTL = 5 * 60_000 // 5 minutes

// ─── 状态 ──────────────────────────────────────────

let ws: WebSocket | null = null
const isConnected = ref(false)
const reconnectAttempts = ref(0)
const isReconnecting = ref(false)

let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let pongTimer: ReturnType<typeof setTimeout> | null = null

const handlers = new Map<string, Set<MessageHandler>>()
const pendingRequests = new Map<string, { resolve: (value: WsMessage) => void; timer: ReturnType<typeof setTimeout> }>()
const pendingMessages: PendingMessage[] = []

// ─── URL 计算 ──────────────────────────────────────

function getWsUrl(): string {
  const envUrl = import.meta.env.VITE_WS_URL as string | undefined
  if (envUrl) return envUrl

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws`
}

// ─── 连接管理 ──────────────────────────────────────

function connect(): void {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }

  const url = getWsUrl()

  try {
    ws = new WebSocket(url)
  } catch {
    scheduleReconnect()
    return
  }

  ws.onopen = () => {
    isConnected.value = true
    reconnectAttempts.value = 0
    isReconnecting.value = false
    startHeartbeat()
    flushPendingMessages()
    emit('open')
  }

  ws.onmessage = (event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data) as WsMessage
      handleMessage(message)
    } catch {
      // 忽略无法解析的消息
    }
  }

  ws.onclose = () => {
    isConnected.value = false
    stopHeartbeat()
    ws = null
    emit('close')
    scheduleReconnect()
  }

  ws.onerror = () => {
    // onclose 会在 onerror 之后触发，无需额外处理
    emit('error')
  }
}

function disconnect(): void {
  clearReconnectTimer()
  stopHeartbeat()

  if (ws) {
    ws.onclose = null // 阻止自动重连
    ws.close()
    ws = null
  }

  isConnected.value = false
  isReconnecting.value = false
  reconnectAttempts.value = 0
}

// ─── 重连 ──────────────────────────────────────────

function scheduleReconnect(): void {
  if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
    isReconnecting.value = false
    emit('reconnect_failed')
    return
  }

  isReconnecting.value = true
  const delay = RECONNECT_DELAYS[reconnectAttempts.value]
  reconnectAttempts.value++

  reconnectTimer = setTimeout(() => {
    connect()
  }, delay)
}

function clearReconnectTimer(): void {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

// ─── 心跳 ──────────────────────────────────────────

function startHeartbeat(): void {
  stopHeartbeat()
  heartbeatTimer = setInterval(() => {
    sendRaw({ type: 'ping' })

    pongTimer = setTimeout(() => {
      // pong 超时，主动断开触发重连
      ws?.close()
    }, PONG_TIMEOUT)
  }, HEARTBEAT_INTERVAL)
}

function stopHeartbeat(): void {
  if (heartbeatTimer !== null) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
  if (pongTimer !== null) {
    clearTimeout(pongTimer)
    pongTimer = null
  }
}

// ─── 消息处理 ──────────────────────────────────────

function handleMessage(message: WsMessage): void {
  // pong 消息：取消超时定时器
  if (message.type === 'pong') {
    if (pongTimer !== null) {
      clearTimeout(pongTimer)
      pongTimer = null
    }
    return
  }

  // 带 requestId 的消息：匹配等待中的请求
  if (message.requestId) {
    const pending = pendingRequests.get(message.requestId)
    if (pending) {
      clearTimeout(pending.timer)
      pendingRequests.delete(message.requestId)
      pending.resolve(message)
      // 不 return，继续触发 type 监听器（某些场景两者都需要）
    }
  }

  emit(message.type, message)
}

// ─── 发送 ──────────────────────────────────────────

function sendRaw(data: Record<string, unknown>): boolean {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data))
    return true
  }
  return false
}

/**
 * 发送消息，返回是否成功写入（或已缓存）
 */
function send(data: Record<string, unknown>): boolean {
  if (sendRaw(data)) return true

  // 断连时缓存消息
  if (pendingMessages.length < MAX_PENDING_MESSAGES) {
    pendingMessages.push({ data, timestamp: Date.now() })
  }
  return false
}

/**
 * 发送请求并等待响应（通过 requestId 匹配）
 *
 * @param type 消息类型
 * @param payload 消息负载
 * @param timeoutMs 超时毫秒数
 * @returns 匹配的响应消息
 */
function sendAndWait(
  type: ClientMessageType,
  payload: Record<string, unknown>,
  timeoutMs = 30_000,
): Promise<WsMessage> {
  const requestId = crypto.randomUUID()

  return new Promise<WsMessage>((resolve, reject) => {
    const timer = setTimeout(() => {
      pendingRequests.delete(requestId)
      reject(new Error(`WebSocket 请求超时: ${type} (${timeoutMs}ms)`))
    }, timeoutMs)

    pendingRequests.set(requestId, { resolve, timer })

    const sent = send({ type, requestId, ...payload })
    if (!sent) {
      clearTimeout(timer)
      pendingRequests.delete(requestId)
      reject(new Error('WebSocket 未连接'))
    }
  })
}

function flushPendingMessages(): void {
  const now = Date.now()
  // 过期消息丢弃
  const valid = pendingMessages.filter((m) => now - m.timestamp < PENDING_MESSAGE_TTL)
  pendingMessages.length = 0

  for (const msg of valid) {
    sendRaw(msg.data)
  }
}

// ─── 事件系统 ──────────────────────────────────────

function on(type: string, handler: MessageHandler): void {
  if (!handlers.has(type)) {
    handlers.set(type, new Set())
  }
  handlers.get(type)!.add(handler)
}

function off(type: string, handler: MessageHandler): void {
  handlers.get(type)?.delete(handler)
}

function emit(type: string, message?: WsMessage): void {
  const typeHandlers = handlers.get(type)
  if (!typeHandlers) return
  for (const handler of typeHandlers) {
    try {
      handler(message ?? { type: type as ServerMessageType })
    } catch {
      // 防止单个处理器异常影响其他处理器
    }
  }
}

// ─── 导出 ──────────────────────────────────────────

export const wsClient = {
  // 状态
  isConnected,
  reconnectAttempts,
  isReconnecting,

  // 连接
  connect,
  disconnect,

  // 发送
  send,
  sendAndWait,
  sendRaw,

  // 事件
  on,
  off,
} as const
