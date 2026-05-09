/** 任务查询 API
 *
 * - 单任务实时状态：WebSocket
 * - 任务列表/删除：REST HTTP
 */

import client from '@/api/client'
import { wsClient } from './wsClient'
import type { WsMessage } from './wsClient'
import type { TaskStatusResponse } from '@/api/types/task'

/** 分页任务列表响应 */
export interface TaskListResponse {
  items: TaskStatusResponse[]
  total: number
}

/** 查询单个任务状态（WebSocket） */
export async function getTaskStatus(taskId: string): Promise<WsMessage> {
  return wsClient.sendAndWait('get_task_status', { taskId })
}

/** 获取任务列表（REST，从后端 SQLite + 内存） */
export async function getTaskList(
  limit = 20,
  offset = 0,
): Promise<TaskListResponse> {
  return client.get('/v1/tasks', {
    params: { limit, offset },
  })
}

/** 删除任务（REST） */
export async function deleteTask(taskId: string): Promise<void> {
  await client.delete(`/v1/tasks/${taskId}`)
}
