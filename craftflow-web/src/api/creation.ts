/**
 * 创作任务 API（WebSocket 驱动）
 *
 * 通过 WebSocket 发送创建/恢复请求。
 * REST 端点保留但不再使用，如需 fallback 可取消注释 REST 调用。
 */

import { wsClient } from './wsClient'
import type { WsMessage } from './wsClient'
import type { CreationRequest } from './types/creation'
import type { ResumeRequest } from './types/resume'

/** 发起创作任务 */
export async function createTask(data: CreationRequest): Promise<WsMessage> {
  return wsClient.sendAndWait('create_creation', {
    topic: data.topic,
    description: data.description,
  })
}

/** 恢复被中断的创作任务（HITL 大纲确认） */
export async function resumeTask(taskId: string, data: ResumeRequest): Promise<WsMessage> {
  return wsClient.sendAndWait('resume_task', {
    taskId,
    action: data.action,
    data: data.data,
  })
}
