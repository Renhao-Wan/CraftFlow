/**
 * 任务详情页 Composable
 *
 * 抽取 TaskDetail.vue 和 PolishingResult.vue 的重复逻辑：
 * - 任务数据获取
 * - 流式内容管理
 * - 显示阶段计算
 * - 生命周期管理（订阅/取消订阅）
 */

import { computed, onMounted, type Ref, type ComputedRef } from 'vue'
import { useTaskStore } from '@/stores/task'
import { useTaskLifecycle } from '@/composables/useTaskLifecycle'
import type { TaskStatusResponse } from '@/api/types/task'

/** 显示阶段 */
export type DisplayPhase = 'waiting' | 'streaming' | 'completed' | 'interrupted' | 'failed'

/** useTaskDetail 返回值 */
export interface UseTaskDetailReturn {
  /** 任务数据 */
  task: ComputedRef<TaskStatusResponse | null>
  /** 流式内容 */
  streamingContent: ComputedRef<string>
  /** 任务级 loading */
  loading: ComputedRef<boolean>
  /** 任务级 error */
  taskError: ComputedRef<string | null>
  /** 显示阶段 */
  displayPhase: ComputedRef<DisplayPhase>
  /** 渲染内容 */
  displayContent: ComputedRef<string>
}

/**
 * 判断任务是否处于终态
 */
function isTerminalStatus(status: string | undefined): boolean {
  return status === 'completed' || status === 'failed'
}

/**
 * 任务详情页 Composable
 *
 * @param taskId 任务 ID 的 Ref
 * @returns 任务详情相关的响应式数据
 */
export function useTaskDetail(taskId: Ref<string>): UseTaskDetailReturn {
  const taskStore = useTaskStore()
  const { loadTask } = useTaskLifecycle()

  // 任务数据：直接按 taskId 从 store 获取
  const task = computed(() => taskStore.getTask(taskId.value) ?? null)

  // 流式内容：直接按 taskId 从 store 获取
  const streamingContent = computed(() => taskStore.getStreamingContent(taskId.value))

  // 任务级 loading 和 error
  const loading = computed(() => taskStore.getTaskLoading(taskId.value))
  const taskError = computed(() => taskStore.getTaskError(taskId.value))

  /**
   * 显示阶段：解耦 UI 状态与任务 status，避免 status 先于 result 到达导致闪烁
   * - 'waiting'：无内容，显示居中等待
   * - 'streaming'：有流式内容，显示实时渲染
   * - 'completed'：有最终结果，显示完成视图
   * - 'interrupted'：status 为 interrupted，等待用户输入（大纲确认等）
   * - 'failed'：失败
   */
  const displayPhase = computed<DisplayPhase>(() => {
    if (task.value?.result) return 'completed'
    if (streamingContent.value) return 'streaming'
    if (task.value?.status === 'interrupted') return 'interrupted'
    if (task.value?.status === 'failed') return 'failed'
    return 'waiting'
  })

  /** 渲染内容：优先用最终结果，回退到流式内容 */
  const displayContent = computed(() => task.value?.result || streamingContent.value)

  onMounted(() => {
    const tid = taskId.value
    const currentTask = task.value

    if (currentTask && isTerminalStatus(currentTask.status)) {
      // 终态任务：result 已在 store 中，直接展示
      return
    }

    // 运行中任务或新任务：订阅 + 获取状态
    // 注意：不在 onUnmounted 中取消订阅，保持订阅以继续接收流式内容
    loadTask(tid)
  })

  return {
    task,
    streamingContent,
    loading,
    taskError,
    displayPhase,
    displayContent,
  }
}
