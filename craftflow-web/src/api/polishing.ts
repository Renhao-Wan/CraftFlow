/**
 * 润色任务 API（WebSocket 驱动）
 *
 * 通过 WebSocket 发送润色请求。
 * REST 端点保留但不再使用。
 */

import { wsClient } from './wsClient'
import type { WsMessage } from './wsClient'
import type { PolishingRequest } from './types/polishing'

/** 发起润色任务 */
export async function createPolishingTask(data: PolishingRequest): Promise<WsMessage> {
  return wsClient.sendAndWait('create_polishing', {
    content: data.content,
    mode: data.mode,
  })
}
