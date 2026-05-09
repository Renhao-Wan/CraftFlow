/**
 * 任务生命周期 Composable（WebSocket 驱动）
 *
 * 封装 任务提交 → WS 推送 → 中断 → 恢复 的完整流程。
 * 组件只需调用 submit/resume 方法，其余逻辑由 composable 管理。
 *
 * 替代原轮询方案：服务端通过 WebSocket 主动推送状态变更。
 */

import { ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { wsClient, type WsMessage } from '@/api/wsClient'
import type { TaskStatus } from '@/api/types/task'
import type { ResumeAction } from '@/api/types/resume'
import type { PolishingMode } from '@/api/types/polishing'

/** 任务类型 */
export type TaskType = 'creation' | 'polishing'

/** 全局 WS 监听器是否已注册 */
let globalListenersRegistered = false

/** 注册全局 WS 任务状态监听器（仅执行一次） */
function ensureGlobalListeners(): void {
  if (globalListenersRegistered) return
  globalListenersRegistered = true

  const taskStore = useTaskStore()

  wsClient.on('task_update', (msg: WsMessage) => {
    taskStore.handleTaskUpdate(msg)
  })

  wsClient.on('task_result', (msg: WsMessage) => {
    taskStore.handleTaskResult(msg)
  })

  wsClient.on('task_error', (msg: WsMessage) => {
    taskStore.handleTaskError(msg)
  })
}

/** 生命周期 Composable 返回值 */
export interface UseTaskLifecycleReturn {
  /** 提交创作任务 */
  submitCreation: (topic: string, description?: string) => Promise<void>
  /** 提交润色任务 */
  submitPolishing: (content: string, mode: PolishingMode) => Promise<void>
  /** HITL 恢复执行 */
  resumeTask: (taskId: string, action: ResumeAction, data?: Record<string, unknown>) => Promise<void>
  /** 加载指定任务状态 */
  loadTask: (taskId: string) => Promise<void>
  /** 取消订阅当前任务的 WS 推送 */
  stop: () => void
  /** 是否正在提交 */
  submitting: ReturnType<typeof ref<boolean>>
  /** 提交错误 */
  submitError: ReturnType<typeof ref<string | null>>
  /** 当前任务类型 */
  taskType: ReturnType<typeof ref<TaskType | null>>
}

/**
 * 任务生命周期 Composable
 *
 * @example
 * ```vue
 * <script setup lang="ts">
 * const { submitCreation, submitting } = useTaskLifecycle()
 *
 * async function onSubmit() {
 *   await submitCreation('主题', '描述')
 *   // 自动跳转到详情页，WS 推送驱动后续状态更新
 * }
 * </script>
 * ```
 */
export function useTaskLifecycle(): UseTaskLifecycleReturn {
  const router = useRouter()
  const taskStore = useTaskStore()

  const submitting = ref(false)
  const submitError = ref<string | null>(null)
  const taskType = ref<TaskType | null>(null)

  // 确保全局 WS 监听器已注册
  ensureGlobalListeners()

  /** 订阅任务的 WS 推送 */
  function subscribeTask(taskId: string): void {
    wsClient.send({ type: 'subscribe_task', taskId })
  }

  /** 提交任务后跳转 */
  async function handleSubmit(taskId: string, type: TaskType): Promise<void> {
    taskType.value = type
    subscribeTask(taskId)

    if (type === 'creation') {
      await router.push({ name: 'task-detail', params: { taskId } })
    } else {
      await router.push({ name: 'polishing-result', params: { taskId } })
    }
  }

  /** 提交创作任务 */
  async function submitCreation(topic: string, description?: string): Promise<void> {
    submitting.value = true
    submitError.value = null
    try {
      const response = await wsClient.sendAndWait('create_creation', {
        topic,
        description,
      })

      const taskId = response.taskId as string
      const status = (response.status as TaskStatus) ?? 'running'

      taskStore.setCurrentTask({
        task_id: taskId,
        status,
        created_at: response.createdAt as string | undefined,
      })

      await handleSubmit(taskId, 'creation')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '提交创作任务失败'
      submitError.value = message
      throw err
    } finally {
      submitting.value = false
    }
  }

  /** 提交润色任务 */
  async function submitPolishing(content: string, mode: PolishingMode): Promise<void> {
    submitting.value = true
    submitError.value = null
    try {
      const response = await wsClient.sendAndWait('create_polishing', {
        content,
        mode,
      })

      const taskId = response.taskId as string
      const status = (response.status as TaskStatus) ?? 'running'

      taskStore.setCurrentTask({
        task_id: taskId,
        status,
        created_at: response.createdAt as string | undefined,
        data: { original_content: content, mode },
      })

      await handleSubmit(taskId, 'polishing')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '提交润色任务失败'
      submitError.value = message
      throw err
    } finally {
      submitting.value = false
    }
  }

  /** HITL 恢复执行 */
  async function resumeTask(
    taskId: string,
    action: ResumeAction,
    data?: Record<string, unknown>,
  ): Promise<void> {
    submitting.value = true
    submitError.value = null
    try {
      const response = await wsClient.sendAndWait('resume_task', {
        taskId,
        action,
        data,
      })

      const responseTaskId = (response.taskId as string) ?? taskId
      const status = (response.status as TaskStatus) ?? 'running'

      taskStore.setCurrentTask({
        task_id: responseTaskId,
        status,
        created_at: response.createdAt as string | undefined,
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '恢复任务失败'
      submitError.value = message
      throw err
    } finally {
      submitting.value = false
    }
  }

  /** 加载指定任务状态 */
  async function loadTask(taskId: string): Promise<void> {
    subscribeTask(taskId)
    await taskStore.fetchTaskStatus(taskId)
  }

  /** 取消订阅当前任务 */
  function stop(): void {
    const taskId = taskStore.currentTask?.task_id
    if (taskId) {
      wsClient.send({ type: 'unsubscribe_task', taskId })
    }
  }

  // 不在 onUnmounted 中自动取消订阅。
  // 原因：提交任务后 router.push 会触发当前组件卸载，但新组件会立即
  // 挂载并接管订阅。如果在卸载时取消订阅，会丢失中间的进度推送。
  // 组件应在适当时机显式调用 stop()（如用户主动离开任务页）。

  return {
    submitCreation,
    submitPolishing,
    resumeTask,
    loadTask,
    stop,
    submitting,
    submitError,
    taskType,
  }
}
