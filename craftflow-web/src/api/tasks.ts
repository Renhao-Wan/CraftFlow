/** 任务查询 API（REST HTTP） */

import client from '@/api/client'
import type { TaskStatusResponse } from '@/api/types/task'

/** 分页任务列表响应 */
export interface TaskListResponse {
  items: TaskStatusResponse[]
  total: number
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

/** 清空所有任务（REST） */
export async function deleteAllTasks(): Promise<{ deleted: number }> {
  return client.delete('/v1/tasks')
}
