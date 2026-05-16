import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { wsClient, type WsMessage } from '@/api/wsClient'
import { getTaskList as apiGetTaskList, deleteTask as apiDeleteTask } from '@/api/tasks'
import type { TaskStatus, TaskStatusResponse } from '@/api/types/task'

/** 判断任务是否处于终态 */
function isTerminalStatus(status: string | undefined): boolean {
  return status === 'completed' || status === 'failed'
}

/** localStorage 流式内容缓存 key 前缀 */
const STREAMING_CACHE_PREFIX = 'craftflow_streaming_'

/** 从 localStorage 恢复流式内容 */
function restoreStreamingFromCache(taskId: string): string {
  try {
    return localStorage.getItem(STREAMING_CACHE_PREFIX + taskId) ?? ''
  } catch {
    return ''
  }
}

/** 保存流式内容到 localStorage */
function saveStreamingToCache(taskId: string, content: string): void {
  try {
    if (content) {
      localStorage.setItem(STREAMING_CACHE_PREFIX + taskId, content)
    } else {
      localStorage.removeItem(STREAMING_CACHE_PREFIX + taskId)
    }
  } catch {
    // localStorage 满或不可用时静默失败
  }
}

/** 清除 localStorage 中的流式内容缓存 */
function clearStreamingCache(taskId: string): void {
  try {
    localStorage.removeItem(STREAMING_CACHE_PREFIX + taskId)
  } catch {
    // 静默失败
  }
}

export const useTaskStore = defineStore('task', () => {
  // ─── State ──────────────────────────────────────────────

  /** 运行中任务实时状态：taskId → 任务状态（WebSocket 推送更新） */
  const tasks = ref<Map<string, TaskStatusResponse>>(new Map())

  /** 历史任务列表：直接从 REST API 获取，仅 completed/failed */
  const taskList = ref<TaskStatusResponse[]>([])
  /** 历史列表总数 */
  const listTotal = ref(0)

  /** 运行中任务列表：直接从 REST API 获取，仅 running/interrupted */
  const runningItems = ref<TaskStatusResponse[]>([])
  /** 运行中列表总数 */
  const runningTotal = ref(0)
  /** 运行中列表当前页 */
  const runningCurrentPage = ref(1)

  /** 多任务流式内容：taskId → 累积内容 */
  const streamingContents = ref<Map<string, string>>(new Map())

  /** 按任务隔离的 loading 状态 */
  const taskLoading = ref<Map<string, boolean>>(new Map())
  /** 按任务隔离的 error 状态 */
  const taskErrors = ref<Map<string, string | null>>(new Map())

  /** 分页元数据 */
  const currentPage = ref(1)
  const pageSize = ref(5)

  /** 全局 loading（用于任务列表等） */
  const loading = ref(false)
  /** 全局 error（用于任务列表等） */
  const error = ref<string | null>(null)

  // ─── Getters ────────────────────────────────────────────

  const totalPages = computed(() => Math.ceil(listTotal.value / pageSize.value))
  const runningTotalPages = computed(() => Math.ceil(runningTotal.value / pageSize.value))

  // ─── Actions ────────────────────────────────────────────

  /** 获取指定任务状态（优先从 tasks Map，否则从 taskList） */
  function getTask(taskId: string): TaskStatusResponse | undefined {
    return tasks.value.get(taskId) ?? taskList.value.find((t) => t.task_id === taskId)
  }

  /** 获取指定任务的流式内容 */
  function getStreamingContent(taskId: string): string {
    // 优先从内存 Map 获取
    const memContent = streamingContents.value.get(taskId)
    if (memContent) return memContent
    // 回退到 localStorage 缓存
    return restoreStreamingFromCache(taskId)
  }

  /** 获取指定任务的 loading 状态 */
  function getTaskLoading(taskId: string): boolean {
    return taskLoading.value.get(taskId) ?? false
  }

  /** 获取指定任务的 error 状态 */
  function getTaskError(taskId: string): string | null {
    return taskErrors.value.get(taskId) ?? null
  }

  /** 设置指定任务的 loading 状态 */
  function setTaskLoading(taskId: string, isLoading: boolean): void {
    taskLoading.value.set(taskId, isLoading)
  }

  /** 设置指定任务的 error 状态 */
  function setTaskError(taskId: string, errorMsg: string | null): void {
    taskErrors.value.set(taskId, errorMsg)
  }

  /** 移除指定任务数据 */
  function removeTask(taskId: string): void {
    tasks.value.delete(taskId)
    streamingContents.value.delete(taskId)
    clearStreamingCache(taskId)
    taskLoading.value.delete(taskId)
    taskErrors.value.delete(taskId)
    // 从历史列表中移除
    taskList.value = taskList.value.filter((t) => t.task_id !== taskId)
    // 从运行中列表移除
    runningItems.value = runningItems.value.filter((t) => t.task_id !== taskId)
  }

  /** 通过 WebSocket 查询任务状态 */
  async function fetchTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    setTaskLoading(taskId, true)
    setTaskError(taskId, null)
    try {
      const response = await wsClient.sendAndWait('get_task_status', { taskId })
      const statusData: TaskStatusResponse = {
        task_id: (response.taskId as string) ?? taskId,
        status: (response.status as TaskStatus) ?? 'running',
        current_node: response.currentNode as string | undefined,
        current_node_label: response.currentNodeLabel as string | undefined,
        awaiting: response.awaiting as string | undefined,
        data: response.data as Record<string, unknown> | undefined,
        result: response.result as string | undefined,
        fact_check_result: response.factCheckResult as string | undefined,
        error: response.error as string | undefined,
        progress: response.progress as number | undefined,
        created_at: response.createdAt as string | undefined,
        updated_at: response.updatedAt as string | undefined,
      }
      // 合并到已有数据，保留 REST 获取的 topic 等 WS 响应中没有的字段
      const existing = tasks.value.get(taskId)
      const merged = existing ? { ...existing, ...statusData } : statusData
      tasks.value.set(taskId, merged)
      return merged
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '获取任务状态失败'
      setTaskError(taskId, message)
      throw err
    } finally {
      setTaskLoading(taskId, false)
    }
  }

  /** 获取任务列表（REST），数据存储到 taskList 和 runningItems */
  async function fetchTaskList(
    page?: number,
    tab: 'history' | 'running' = 'history',
  ): Promise<void> {
    loading.value = true
    error.value = null
    if (tab === 'history' && page !== undefined) currentPage.value = page
    if (tab === 'running' && page !== undefined) runningCurrentPage.value = page

    const offset = (currentPage.value - 1) * pageSize.value
    const runningOffset = (runningCurrentPage.value - 1) * pageSize.value
    try {
      const response = await apiGetTaskList(pageSize.value, offset, pageSize.value, runningOffset)
      runningItems.value = response.running_items
      runningTotal.value = response.running_total
      taskList.value = response.items
      listTotal.value = response.total
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '获取任务列表失败'
    } finally {
      loading.value = false
    }
  }

  /** 删除任务（REST），成功后重新拉取当前页以保持状态一致 */
  async function deleteTask(taskId: string): Promise<void> {
    await apiDeleteTask(taskId)
    removeTask(taskId)
    await fetchTaskList(currentPage.value)
  }

  /** 处理 WS task_update 推送 */
  function handleTaskUpdate(message: WsMessage): void {
    const taskId = message.taskId as string
    if (!taskId) return

    let existing = tasks.value.get(taskId)
    // 如果任务不在 Map 中，创建占位条目
    if (!existing) {
      existing = { task_id: taskId, status: 'running', created_at: new Date().toISOString() }
    }

    const newStatus = (message.status as TaskStatus) ?? existing.status ?? 'running'

    // 如果 task_update 携带 completed 状态但没有 result，暂不更新 status
    // 等待 task_result 消息携带完整结果后再更新，避免闪烁
    if (newStatus === 'completed' && !message.result && !existing.result) {
      const updated: TaskStatusResponse = {
        ...existing,
        current_node: (message.currentNode as string) ?? existing.current_node,
        current_node_label: (message.currentNodeLabel as string) ?? existing.current_node_label,
        awaiting: (message.awaiting as string) ?? undefined,
        data: (message.data as Record<string, unknown>) ?? existing.data,
        error: (message.error as string) ?? existing.error,
        progress: (message.progress as number) ?? existing.progress,
        updated_at: new Date().toISOString(),
      }
      tasks.value.set(taskId, updated)
      return
    }

    const updated: TaskStatusResponse = {
      ...existing,
      status: newStatus,
      current_node: (message.currentNode as string) ?? existing.current_node,
      current_node_label: (message.currentNodeLabel as string) ?? existing.current_node_label,
      // 非 interrupted 状态时显式清除 awaiting，避免残留旧值
      awaiting: newStatus === 'interrupted'
        ? ((message.awaiting as string) ?? existing.awaiting)
        : undefined,
      data: (message.data as Record<string, unknown>) ?? existing.data,
      error: (message.error as string) ?? existing.error,
      progress: (message.progress as number) ?? existing.progress,
      updated_at: new Date().toISOString(),
    }
    tasks.value.set(taskId, updated)
  }

  /** 处理 WS task_token 推送（ReducerNode 流式输出） */
  function handleTaskToken(message: WsMessage): void {
    const taskId = message.taskId as string
    if (!taskId) return
    const content = (message.content as string) ?? ''
    const existing = streamingContents.value.get(taskId) ?? ''
    const newContent = existing + content
    streamingContents.value.set(taskId, newContent)
    // 同步保存到 localStorage，确保离开页面后能恢复
    saveStreamingToCache(taskId, newContent)
  }

  /** 处理 WS task_result 推送 */
  function handleTaskResult(message: WsMessage): void {
    const taskId = message.taskId as string
    if (!taskId) return

    // 清空该任务的流式内容（最终结果由 result 承载）
    streamingContents.value.delete(taskId)
    clearStreamingCache(taskId)

    const result = (message.result as string) ?? ''
    const factCheckResult = (message.factCheckResult as string) ?? ''
    const data = message.data as Record<string, unknown> | undefined
    const now = new Date().toISOString()

    const existing = tasks.value.get(taskId)
    const updated: TaskStatusResponse = {
      ...(existing ?? { task_id: taskId }),
      status: 'completed',
      result,
      fact_check_result: factCheckResult || existing?.fact_check_result,
      data: data ?? existing?.data,
      progress: 100,
      created_at: existing?.created_at ?? (message.createdAt as string) ?? now,
      updated_at: (message.updatedAt as string) ?? now,
    }
    tasks.value.set(taskId, updated)
    // 任务完成，从运行中列表移除
    runningItems.value = runningItems.value.filter((t) => t.task_id !== taskId)
  }
  function handleTaskError(message: WsMessage): void {
    const taskId = message.taskId as string
    if (!taskId) return

    const errorMsg = (message.error as string) ?? '未知错误'
    const now = new Date().toISOString()

    const existing = tasks.value.get(taskId)
    const updated: TaskStatusResponse = {
      ...(existing ?? { task_id: taskId }),
      status: 'failed',
      error: errorMsg,
      progress: 0,
      created_at: existing?.created_at ?? now,
      updated_at: now,
    }
    tasks.value.set(taskId, updated)
    // 任务失败，从运行中列表移除
    runningItems.value = runningItems.value.filter((t) => t.task_id !== taskId)
  }

  /** 设置当前任务（合并更新，保留已有字段） */
  function setCurrentTask(task: TaskStatusResponse): void {
    const existing = tasks.value.get(task.task_id)
    if (existing) {
      tasks.value.set(task.task_id, { ...existing, ...task })
    } else {
      tasks.value.set(task.task_id, task)
    }
  }

  return {
    // state
    tasks,
    taskList,
    runningItems,
    runningTotal,
    runningCurrentPage,
    streamingContents,
    listTotal,
    currentPage,
    pageSize,
    loading,
    error,
    // getters
    totalPages,
    runningTotalPages,
    // actions
    getTask,
    getStreamingContent,
    getTaskLoading,
    getTaskError,
    setTaskLoading,
    setTaskError,
    removeTask,
    fetchTaskStatus,
    fetchTaskList,
    deleteTask,
    handleTaskUpdate,
    handleTaskResult,
    handleTaskToken,
    handleTaskError,
    setCurrentTask,
  }
})
