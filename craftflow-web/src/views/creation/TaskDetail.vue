<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useTaskLifecycle } from '@/composables/useTaskLifecycle'
import TaskStatusBadge from '@/components/common/TaskStatusBadge.vue'
import ProgressBar from '@/components/common/ProgressBar.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import OutlineEditor from '@/components/creation/OutlineEditor.vue'
import type { OutlineItem } from '@/components/creation/OutlineEditor.vue'

const props = defineProps<{ taskId: string }>()

const router = useRouter()
const taskStore = useTaskStore()
const { resumeTask, loadTask, stop, submitting, submitError } = useTaskLifecycle()

const copied = ref(false)

const task = computed(() => taskStore.currentTask)
const isNotFound = computed(
  () => taskStore.error?.includes('404') ?? false,
)
const status = computed(() => task.value?.status)
const progress = computed(() => task.value?.progress ?? 0)
const currentNode = computed(() => task.value?.current_node_label ?? task.value?.current_node ?? '')
const result = computed(() => task.value?.result ?? '')
const error = computed(() => task.value?.error ?? '未知错误')

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

async function onRetry(): Promise<void> {
  taskStore.clearCurrentTask()
  await loadTask(props.taskId)
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

function onBack(): void {
  router.back()
}

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
      <!-- running -->
      <div v-if="status === 'running'" class="state-running">
        <div class="running-header">
          <LoadingSpinner :size="28" label="" />
          <div>
            <h2 class="state-title">正在创作中...</h2>
            <p v-if="currentNode" class="current-node">
              当前阶段：{{ currentNode }}
            </p>
          </div>
        </div>
        <ProgressBar
          :percentage="progress"
          :show-text="true"
          :height="10"
        />
      </div>

      <!-- interrupted -->
      <div v-else-if="status === 'interrupted'" class="state-interrupted">
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

      <!-- completed -->
      <div v-else-if="status === 'completed'" class="state-completed">
        <div class="result-header">
          <h2 class="state-title">创作完成</h2>
          <button class="copy-btn" @click="onCopy">
            {{ copied ? '已复制' : '复制全文' }}
          </button>
        </div>
        <div class="result-body">
          <MarkdownRenderer v-if="result" :content="result" />
          <p v-else class="empty-hint">暂无结果内容</p>
        </div>
      </div>

      <!-- failed -->
      <div v-else-if="status === 'failed'" class="state-failed">
        <h2 class="state-title">创作失败</h2>
        <ErrorAlert
          :message="error"
          :retryable="true"
          @retry="onRetry"
        />
      </div>
    </template>
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

/* running */
.state-running {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  padding: var(--space-xl);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.running-header {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.current-node {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 4px 0 0;
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

.copy-btn {
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

.copy-btn:hover {
  background: #eaddd7;
}

.result-body {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  background: var(--color-bg-surface);
}

/* failed */
.state-failed {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  padding: var(--space-xl);
  background: #fef2f2;
  border: 1px solid #fecaca;
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

@media (max-width: 768px) {
  .state-running {
    padding: var(--space-lg);
  }
}
</style>
