import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { wsClient, type WsMessage } from '@/api/wsClient'
import { getTaskList as apiGetTaskList, deleteTask as apiDeleteTask } from '@/api/tasks'
import type { TaskStatus, TaskStatusResponse } from '@/api/types/task'

export const useTaskStore = defineStore('task', () => {
  // ─── State ──────────────────────────────────────────────
  const currentTask = ref<TaskStatusResponse | null>(null)
  const taskList = ref<TaskStatusResponse[]>([])
  const taskTotal = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(5)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ─── Getters ────────────────────────────────────────────
  const isRunning = computed(() => currentTask.value?.status === 'running')
  const isInterrupted = computed(() => currentTask.value?.status === 'interrupted')
  const isCompleted = computed(() => currentTask.value?.status === 'completed')
  const isFailed = computed(() => currentTask.value?.status === 'failed')
  const isTerminal = computed(() => isCompleted.value || isFailed.value)

  // ─── Actions ────────────────────────────────────────────

  /** 通过 WebSocket 查询任务状态 */
  async function fetchTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    loading.value = true
    error.value = null
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
      currentTask.value = statusData
      return statusData
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '获取任务状态失败'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  /** 获取任务列表（REST，从后端 SQLite + 内存） */
  async function fetchTaskList(page?: number): Promise<void> {
    loading.value = true
    error.value = null
    if (page !== undefined) {
      currentPage.value = page
    }
    const offset = (currentPage.value - 1) * pageSize.value
    try {
      const response = await apiGetTaskList(pageSize.value, offset)
      taskList.value = response.items
      taskTotal.value = response.total
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '获取任务列表失败'
    } finally {
      loading.value = false
    }
  }

  /** 总页数 */
  const totalPages = computed(() => Math.ceil(taskTotal.value / pageSize.value))

  /** 删除任务（REST） */
  async function deleteTask(taskId: string): Promise<void> {
    await apiDeleteTask(taskId)
    taskList.value = taskList.value.filter((t) => t.task_id !== taskId)
    if (currentTask.value?.task_id === taskId) {
      currentTask.value = null
    }
  }

  /** 处理 WS task_update 推送 */
  function handleTaskUpdate(message: WsMessage): void {
    const taskId = message.taskId as string
    if (!taskId || !currentTask.value || currentTask.value.task_id !== taskId) return

    const newStatus = (message.status as TaskStatus) ?? currentTask.value.status

    // 如果 task_update 携带 completed 状态但没有 result，暂不更新 status
    // 等待 task_result 消息携带完整结果后再更新，避免闪烁
    if (newStatus === 'completed' && !message.result && !currentTask.value.result) {
      // 只更新非 status 字段
      currentTask.value = {
        ...currentTask.value,
        current_node: (message.currentNode as string) ?? currentTask.value.current_node,
        current_node_label: (message.currentNodeLabel as string) ?? currentTask.value.current_node_label,
        awaiting: (message.awaiting as string) ?? undefined,
        data: (message.data as Record<string, unknown>) ?? currentTask.value.data,
        error: (message.error as string) ?? currentTask.value.error,
        progress: (message.progress as number) ?? currentTask.value.progress,
        updated_at: new Date().toISOString(),
      }
      return
    }

    currentTask.value = {
      ...currentTask.value,
      status: newStatus,
      current_node: (message.currentNode as string) ?? currentTask.value.current_node,
      current_node_label: (message.currentNodeLabel as string) ?? currentTask.value.current_node_label,
      awaiting: (message.awaiting as string) ?? undefined,
      data: (message.data as Record<string, unknown>) ?? currentTask.value.data,
      error: (message.error as string) ?? currentTask.value.error,
      progress: (message.progress as number) ?? currentTask.value.progress,
      updated_at: new Date().toISOString(),
    }
  }

  /** 处理 WS task_result 推送 */
  function handleTaskResult(message: WsMessage): void {
    const taskId = message.taskId as string
    if (!taskId) return

    const result = (message.result as string) ?? ''
    const factCheckResult = (message.factCheckResult as string) ?? ''
    const data = message.data as Record<string, unknown> | undefined
    const now = new Date().toISOString()

    if (currentTask.value && currentTask.value.task_id === taskId) {
      currentTask.value = {
        ...currentTask.value,
        status: 'completed',
        result,
        fact_check_result: factCheckResult || currentTask.value.fact_check_result,
        data: data ?? currentTask.value.data,
        progress: 100,
        updated_at: (message.updatedAt as string) ?? now,
      }
    } else {
      // task_result 可能先于 task_update 到达（currentTask 为 null）
      // 或 currentTask 存在但 task_id 不匹配（切换了任务）
      currentTask.value = {
        task_id: taskId,
        status: 'completed',
        result,
        fact_check_result: factCheckResult,
        data,
        progress: 100,
        created_at: (message.createdAt as string) ?? now,
        updated_at: (message.updatedAt as string) ?? now,
      }
    }
  }

  /** 处理 WS task_error 推送 */
  function handleTaskError(message: WsMessage): void {
    const taskId = message.taskId as string
    if (!taskId) return

    const errorMsg = (message.error as string) ?? '未知错误'
    const now = new Date().toISOString()

    if (currentTask.value && currentTask.value.task_id === taskId) {
      currentTask.value = {
        ...currentTask.value,
        status: 'failed',
        error: errorMsg,
        progress: 0,
        updated_at: now,
      }
    } else {
      currentTask.value = {
        task_id: taskId,
        status: 'failed',
        error: errorMsg,
        progress: 0,
        created_at: now,
        updated_at: now,
      }
    }
  }

  /** 清除当前任务 */
  function clearCurrentTask(): void {
    currentTask.value = null
    error.value = null
  }

  /** 设置当前任务（用于从外部直接注入状态） */
  function setCurrentTask(task: TaskStatusResponse): void {
    currentTask.value = task
  }

  return {
    // state
    currentTask,
    taskList,
    taskTotal,
    currentPage,
    pageSize,
    loading,
    error,
    // getters
    isRunning,
    isInterrupted,
    isCompleted,
    isFailed,
    isTerminal,
    totalPages,
    // actions
    fetchTaskStatus,
    fetchTaskList,
    deleteTask,
    handleTaskUpdate,
    handleTaskResult,
    handleTaskError,
    clearCurrentTask,
    setCurrentTask,
  }
})
