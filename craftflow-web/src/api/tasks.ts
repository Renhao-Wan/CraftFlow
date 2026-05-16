/** 任务查询 API（REST HTTP） */

import client from '@/api/client'
import type { TaskStatusResponse } from '@/api/types/task'

/** 分页任务列表响应（双列表：运行中 + 历史） */
export interface TaskListResponse {
  running_items: TaskStatusResponse[]
  running_total: number
  items: TaskStatusResponse[]
  total: number
}

/** 获取任务列表（REST，运行中从内存，历史从 SQLite） */
export async function getTaskList(
  limit = 5,
  offset = 0,
  runningLimit = 5,
  runningOffset = 0,
): Promise<TaskListResponse> {
  return client.get('/v1/tasks', {
    params: { limit, offset, running_limit: runningLimit, running_offset: runningOffset },
  })
}

/** 删除任务（REST） */
export async function deleteTask(taskId: string): Promise<void> {
  await client.delete(`/v1/tasks/${taskId}`)
}

/** 按状态清空任务（REST） */
export async function deleteTasksByStatus(statuses: string[]): Promise<{ deleted: number }> {
  return client.delete('/v1/tasks', { params: { statuses: statuses.join(',') } })
}
