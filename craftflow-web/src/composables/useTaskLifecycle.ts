/**
 * 任务生命周期 Composable（WebSocket 驱动）
 *
 * 封装 任务提交 → WS 推送 → 中断 → 恢复 的完整流程。
 * 组件只需调用 submit/resume 方法，其余逻辑由 composable 管理。
 *
 * 替代原轮询方案：服务端通过 WebSocket 主动推送状态变更。
 */

import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useNavigationStore } from '@/stores/navigation'
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

  // 清除旧处理器，防止 HMR 重新执行模块后监听器累积导致 token 重复
  const eventTypes = ['task_update', 'task_result', 'task_token', 'task_error'] as const
  for (const type of eventTypes) {
    wsClient.clearTypeHandlers(type)
  }

  wsClient.on('task_update', (msg: WsMessage) => {
    taskStore.handleTaskUpdate(msg)
  })

  wsClient.on('task_result', (msg: WsMessage) => {
    taskStore.handleTaskResult(msg)
    // 任务完成，自动取消订阅
    const taskId = msg.taskId as string
    if (taskId) {
      wsClient.unsubscribeTask(taskId)
    }
  })

  wsClient.on('task_token', (msg: WsMessage) => {
    taskStore.handleTaskToken(msg)
  })

  wsClient.on('task_error', (msg: WsMessage) => {
    taskStore.handleTaskError(msg)
    // 任务失败，自动取消订阅
    const taskId = msg.taskId as string
    if (taskId) {
      wsClient.unsubscribeTask(taskId)
    }
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
  /** 原地重试创作任务（不跳转页面） */
  retryCreation: (topic: string, description?: string) => Promise<void>
  /** 原地重试润色任务（不跳转页面） */
  retryPolishing: (content: string, mode: PolishingMode) => Promise<void>
  /** 加载指定任务状态 */
  loadTask: (taskId: string) => Promise<void>
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
  const navStore = useNavigationStore()

  const submitting = ref(false)
  const submitError = ref<string | null>(null)
  const taskType = ref<TaskType | null>(null)

  // 确保全局 WS 监听器已注册
  ensureGlobalListeners()

  /** 订阅任务的 WS 推送 */
  function subscribeTask(taskId: string): void {
    wsClient.subscribeTask(taskId)
  }

  /** 提交任务后跳转 */
  async function handleSubmit(taskId: string, type: TaskType): Promise<void> {
    taskType.value = type
    subscribeTask(taskId)

    navStore.setDetailSource(type)
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
        data: { topic, description },
      })

      await handleSubmit(taskId, 'creation')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '提交创作任务失败'
      submitError.value = message
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
        current_node: 'router',
        current_node_label: '路由决策',
        progress: 5,
        created_at: response.createdAt as string | undefined,
        data: { original_content: content, mode },
      })

      await handleSubmit(taskId, 'polishing')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '提交润色任务失败'
      submitError.value = message
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

    // 乐观更新：立即将状态设为 running 并清除 awaiting，避免 UI 停留在 interrupted
    const existing = taskStore.getTask(taskId)
    if (existing) {
      taskStore.setCurrentTask({ ...existing, status: 'running', awaiting: undefined })
    }

    try {
      await wsClient.sendAndWait('resume_task', { taskId, action, data })
      // 不覆盖 store，后续 task_update 推送会携带完整状态
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '恢复任务失败'
      submitError.value = message
      // 回滚乐观更新
      if (existing) {
        taskStore.setCurrentTask(existing)
      }
    } finally {
      submitting.value = false
    }
  }

  /** 原地重试：创建新任务，替换当前页状态，不跳转 */
  async function retryInPlace(
    type: TaskType,
    payload: Record<string, unknown>,
  ): Promise<void> {
    const msgType = type === 'creation' ? 'create_creation' : 'create_polishing'

    submitting.value = true
    submitError.value = null
    try {
      const response = await wsClient.sendAndWait(msgType, payload)
      const newTaskId = response.taskId as string
      const status = (response.status as TaskStatus) ?? 'running'

      taskStore.setCurrentTask({
        task_id: newTaskId,
        status,
        created_at: response.createdAt as string | undefined,
        data: type === 'creation'
          ? { topic: payload.topic, description: payload.description }
          : { original_content: payload.content, mode: payload.mode },
      })

      subscribeTask(newTaskId)
      taskType.value = type

      // 使用 Vue Router 替换路由
      const routeName = type === 'creation' ? 'task-detail' : 'polishing-result'
      await router.replace({ name: routeName, params: { taskId: newTaskId } })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '重试失败'
      submitError.value = message
    } finally {
      submitting.value = false
    }
  }

  async function retryCreation(topic: string, description?: string): Promise<void> {
    await retryInPlace('creation', { topic, description })
  }

  async function retryPolishing(content: string, mode: PolishingMode): Promise<void> {
    await retryInPlace('polishing', { content, mode })
  }

  /** 加载指定任务状态 */
  async function loadTask(taskId: string): Promise<void> {
    subscribeTask(taskId)
    await taskStore.fetchTaskStatus(taskId)
  }

  return {
    submitCreation,
    submitPolishing,
    resumeTask,
    retryCreation,
    retryPolishing,
    loadTask,
    submitting,
    submitError,
    taskType,
  }
}
