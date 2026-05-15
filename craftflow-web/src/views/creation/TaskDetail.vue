<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useTaskLifecycle } from '@/composables/useTaskLifecycle'
import TaskStatusBadge from '@/components/common/TaskStatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import OutlineEditor from '@/components/creation/OutlineEditor.vue'
import BackToTop from '@/components/common/BackToTop.vue'
import { usePdfExport } from '@/composables/usePdfExport'
import type { OutlineItem } from '@/components/creation/OutlineEditor.vue'

const props = defineProps<{ taskId: string }>()

const router = useRouter()
const taskStore = useTaskStore()
const { resumeTask, retryCreation, loadTask, stop, submitting, submitError } = useTaskLifecycle()

const copied = ref(false)
const resultBodyRef = ref<HTMLElement | null>(null)
const { exporting, exportToPdf } = usePdfExport()

const task = computed(() => taskStore.currentTask)
const isNotFound = computed(
  () => taskStore.error?.includes('404') ?? false,
)
const status = computed(() => task.value?.status)
const progress = computed(() => task.value?.progress ?? 0)
const currentNode = computed(() => task.value?.current_node_label ?? task.value?.current_node ?? '')
const result = computed(() => task.value?.result ?? '')
const error = computed(() => task.value?.error ?? '未知错误')
const streamingContent = computed(() => taskStore.streamingContent)

/**
 * 显示阶段：解耦 UI 状态与任务 status，避免 status 先于 result 到达导致闪烁
 * - 'waiting'：无内容，显示居中等待
 * - 'streaming'：有流式内容，显示实时渲染
 * - 'completed'：有最终结果，显示完成视图
 * - 'interrupted'：大纲确认
 * - 'failed'：失败
 */
type DisplayPhase = 'waiting' | 'streaming' | 'completed' | 'interrupted' | 'failed'
const displayPhase = computed<DisplayPhase>(() => {
  if (result.value) return 'completed'
  if (streamingContent.value) return 'streaming'
  if (status.value === 'interrupted') return 'interrupted'
  if (status.value === 'failed') return 'failed'
  return 'waiting'
})

/** 渲染内容：优先用最终结果，回退到流式内容 */
const displayContent = computed(() => result.value || streamingContent.value)

const outlineItems = computed<OutlineItem[]>(() => {
  const raw = task.value?.data
  if (!raw || !Array.isArray(raw.outline)) return []
  return raw.outline as OutlineItem[]
})

function onConfirmOutline(): void {
  resumeTask(props.taskId, 'confirm_outline')
}

function onUpdateOutline(items: OutlineItem[]): void {
  resumeTask(props.taskId, 'update_outline', { outline: items })
}

function onRetry(): void {
  const data = task.value?.data
  const topic = data?.topic as string | undefined
  if (topic) {
    retryCreation(topic, data?.description as string | undefined)
  }
}

async function onCopy(): Promise<void> {
  if (!result.value) return
  try {
    await navigator.clipboard.writeText(result.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    // fallback
  }
}

async function onExport(): Promise<void> {
  if (!resultBodyRef.value || !task.value) return
  const filename = task.value.topic || '创作结果'
  await exportToPdf(resultBodyRef.value, filename)
}

function onBack(): void {
  router.back()
}

// 流式输出时自动滚动到底部（页面级滚动）
watch(streamingContent, () => {
  if (streamingContent.value) {
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' })
  }
})

onMounted(() => {
  if (!task.value || task.value.task_id !== props.taskId) {
    loadTask(props.taskId)
  }
})

let fetchedOnce = false
watch(
  () => ({ status: status.value, result: result.value }),
  (val) => {
    if (val.status === 'completed' && !val.result && !fetchedOnce) {
      fetchedOnce = true
      loadTask(props.taskId)
    }
  },
)

onUnmounted(() => {
  stop()
})
</script>

<template>
  <div class="task-detail-page">
    <!-- 顶部栏 -->
    <div class="detail-topbar">
      <button class="back-btn" @click="onBack">&larr; 返回</button>
      <div class="topbar-meta">
        <TaskStatusBadge v-if="task" :status="task.status" />
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="!task && taskStore.loading" class="state-center">
      <LoadingSpinner :size="32" label="加载任务状态..." />
    </div>

    <!-- 错误 -->
    <ErrorAlert
      v-else-if="taskStore.error && !task && !isNotFound"
      :message="taskStore.error"
      :retryable="true"
      @retry="onRetry"
    />

    <!-- 任务不存在 -->
    <div v-else-if="isNotFound" class="state-center">
      <div class="not-found-hint">
        <p>任务不存在或已过期</p>
        <button class="link-btn" @click="router.push({ name: 'history' })">
          查看历史记录
        </button>
      </div>
    </div>

    <!-- 任务内容 -->
    <template v-else-if="task">
      <!-- interrupted: 大纲确认（独立视图） -->
      <div v-if="displayPhase === 'interrupted'" class="state-interrupted">
        <h2 class="state-title">大纲已生成，请确认</h2>
        <p class="state-desc">
          AI 已根据你的主题生成了文章大纲。你可以直接确认，或点击条目编辑后更新。
        </p>

        <ErrorAlert
          v-if="submitError"
          :message="submitError"
          :retryable="false"
        />

        <OutlineEditor
          v-if="outlineItems.length > 0"
          :items="outlineItems"
          :loading="submitting"
          @confirm="onConfirmOutline"
          @update="onUpdateOutline"
        />
        <div v-else class="state-center">
          <p class="empty-hint">暂无大纲数据</p>
        </div>
      </div>

      <!-- failed: 错误（独立视图） -->
      <div v-else-if="displayPhase === 'failed'" class="state-failed">
        <h2 class="state-title">创作失败</h2>
        <ErrorAlert
          :message="error"
          :retryable="true"
          @retry="onRetry"
        />
      </div>

      <!-- waiting / streaming / completed: 统一容器，标题栏固定 -->
      <div v-else class="state-completed">
        <div class="result-header">
          <div class="header-left">
            <div class="header-spinner" :class="{ visible: displayPhase !== 'completed' }">
              <LoadingSpinner :size="20" label="" />
            </div>
            <h2 class="state-title">
              {{ displayPhase === 'completed' ? '创作完成' : '正在创作中...' }}
            </h2>
            <span v-if="currentNode || progress > 0" class="current-node-tag" :class="{ visible: displayPhase !== 'completed' }">
              {{ currentNode }}{{ currentNode && progress > 0 ? ' · ' : '' }}{{ progress > 0 ? Math.round(progress) + '%' : '' }}
            </span>
          </div>
          <div class="header-right">
            <div class="result-actions" :class="{ visible: displayPhase === 'completed' }">
              <button class="action-btn" @click="onCopy">
                {{ copied ? '已复制' : '复制全文' }}
              </button>
              <button class="action-btn" :disabled="exporting" @click="onExport">
                {{ exporting ? '导出中...' : '导出 PDF' }}
              </button>
            </div>
          </div>
        </div>
        <div ref="resultBodyRef" class="result-body">
          <MarkdownRenderer v-if="displayContent" :content="displayContent" />
          <span v-if="displayPhase === 'streaming'" class="typing-cursor" />
          <div v-else-if="displayPhase === 'waiting'" class="waiting-hint">
            <LoadingSpinner :size="24" label="" />
          </div>
          <p v-else-if="!displayContent" class="empty-hint">暂无结果内容</p>
        </div>
      </div>
    </template>

    <BackToTop />
  </div>
</template>

<style scoped>
.task-detail-page {
  max-width: 800px;
  margin: 0 auto;
  padding-top: var(--space-lg);
  padding-bottom: var(--space-xl);
}

/* 顶部栏 */
.detail-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-lg);
}

.back-btn {
  padding: 6px 14px;
  font-size: 14px;
  color: var(--color-text-secondary);
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.back-btn:hover {
  border-color: var(--color-text-muted);
}

.topbar-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

/* 通用状态 */
.state-center {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
}

.state-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.state-desc {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: var(--space-sm) 0 var(--space-lg);
  line-height: 1.6;
}

.empty-hint {
  font-size: 14px;
  color: var(--color-text-light);
  text-align: center;
  padding: var(--space-lg);
}

.current-node {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 4px 0 0;
}

/* 内容区等待提示 */
.waiting-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl) 0;
}

/* interrupted */
.state-interrupted {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* completed */
.state-completed {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 标题栏左右布局 */
.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.header-right {
  display: flex;
  align-items: center;
}

/* spinner 和 tag 的 opacity 过渡 */
.header-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
}
.header-spinner,
.current-node-tag {
  opacity: 0;
  transition: opacity 300ms ease;
}
.header-spinner.visible,
.current-node-tag.visible {
  opacity: 1;
}

/* 完成按钮的 opacity 过渡 */
.header-right .result-actions {
  opacity: 0;
  transition: opacity 300ms ease;
}
.header-right .result-actions.visible {
  opacity: 1;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-accent);
  background: var(--color-accent-soft);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--color-accent-soft);
  border-color: var(--color-accent);
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.result-body {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  background: var(--color-bg-surface);
}

.current-node-tag {
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-accent-soft);
  padding: 3px 10px;
  border-radius: var(--radius-md);
}

/* failed */
.state-failed {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  padding: var(--space-xl);
  background: var(--color-error-bg);
  border: 1px solid var(--color-error);
  border-radius: var(--radius-lg);
}

/* not found hint */
.not-found-hint {
  text-align: center;
  color: var(--color-text-muted);
}

.not-found-hint p {
  margin: 0 0 12px;
  font-size: 15px;
}

.link-btn {
  font-size: 14px;
  color: var(--color-accent);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
}

.link-btn:hover {
  opacity: 0.7;
}
</style>
