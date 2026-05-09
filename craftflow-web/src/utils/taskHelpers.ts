import type { TaskStatusResponse } from '@/api/types/task'

/** 根据任务数据推断类型（优先使用 graph_type，回退到 data.mode） */
export function inferTaskType(data: TaskStatusResponse): 'creation' | 'polishing' {
  if (data.graph_type) return data.graph_type
  if (data.data && typeof data.data.mode === 'number') return 'polishing'
  return 'creation'
}

/** 格式化 ISO 时间为本地短格式 */
export function formatTime(iso?: string): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

/** 根据任务类型返回对应的详情路由名 */
export function taskRouteName(type: 'creation' | 'polishing'): string {
  return type === 'creation' ? 'task-detail' : 'polishing-result'
}
