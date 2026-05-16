<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useTaskLifecycle } from '@/composables/useTaskLifecycle'
import { useTaskDetail } from '@/composables/useTaskDetail'
import { POLISHING_MODE_META } from '@/api/types/polishing'
import type { PolishingMode } from '@/api/types/polishing'
import TaskStatusBadge from '@/components/common/TaskStatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import BackToTop from '@/components/common/BackToTop.vue'
import { usePdfExport } from '@/composables/usePdfExport'

const props = defineProps<{ taskId: string }>()

const router = useRouter()
const taskStore = useTaskStore()
const { retryPolishing } = useTaskLifecycle()

// 使用 useTaskDetail composable 获取任务详情
const taskIdRef = computed(() => props.taskId)
const {
  task,
  streamingContent,
  loading,
  taskError,
  displayPhase,
  displayContent,
} = useTaskDetail(taskIdRef)

const copied = ref(false)
const viewMode = ref<'result' | 'compare' | 'factCheck'>('result')
const resultBodyRef = ref<HTMLElement | null>(null)
const { exporting, exportToPdf } = usePdfExport()

const isNotFound = computed(
  () => taskError.value?.includes('404') ?? false,
)
const status = computed(() => task.value?.status)
const progress = computed(() => task.value?.progress ?? 0)
const currentNode = computed(() => task.value?.current_node_label ?? task.value?.current_node ?? '')
const result = computed(() => task.value?.result ?? '')
const error = computed(() => task.value?.error ?? '未知错误')
const factCheckResult = computed(() => task.value?.fact_check_result ?? '')

const originalContent = computed(() => {
  const raw = task.value?.data
  if (!raw || typeof raw.original_content !== 'string') return ''
  return raw.original_content
})

const polishingMode = computed<PolishingMode | null>(() => {
  const raw = task.value?.data
  if (!raw || typeof raw.mode !== 'number') return null
  return raw.mode as PolishingMode
})

const modeLabel = computed(() => {
  if (!polishingMode.value) return ''
  return POLISHING_MODE_META[polishingMode.value]?.label ?? ''
})

const isMode3 = computed(() => polishingMode.value === 3)

const accuracyLevel = computed(() => {
  if (!factCheckResult.value) return null
  const match = factCheckResult.value.match(/\*\*总体准确性\*\*[：:]\s*(high|medium|low)/i)
  if (match && match[1]) return match[1].toLowerCase() as 'high' | 'medium' | 'low'
  return null
})

const accuracyDescription = computed(() => {
  switch (accuracyLevel.value) {
    case 'high': return '高准确性'
    case 'medium': return '中等准确性'
    case 'low': return '低准确性'
    default: return ''
  }
})

const accuracyExplanation = computed(() => {
  switch (accuracyLevel.value) {
    case 'high': return '文章内容整体准确，未发现明显事实错误，因此直接返回原文。可以根据审查结果手动进行更改和润色。'
    case 'medium': return '文章存在部分事实问题，已进入修正流程进行优化。'
    case 'low': return '文章存在较多事实错误，已强制进入修正流程进行修正。'
    default: return ''
  }
})

const accuracyClass = computed(() => {
  switch (accuracyLevel.value) {
    case 'high': return 'accuracy-high'
    case 'medium': return 'accuracy-medium'
    case 'low': return 'accuracy-low'
    default: return ''
  }
})

function onRetry(): void {
  if (originalContent.value && polishingMode.value) {
    retryPolishing(originalContent.value, polishingMode.value)
  }
}

async function onCopy(): Promise<void> {
  if (!result.value) return
  try {
    await navigator.clipboard.writeText(result.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    // clipboard API not available
  }
}

async function onExport(): Promise<void> {
  if (!resultBodyRef.value || !task.value) return
  const filename = task.value.topic || '润色结果'
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

// 任务完成但无 result 时，重新获取状态
let fetchedOnce = false
watch(
  () => ({ status: status.value, result: result.value }),
  (val) => {
    if (val.status === 'completed' && !val.result && !fetchedOnce) {
      fetchedOnce = true
      taskStore.fetchTaskStatus(props.taskId)
    }
  },
)
</script>

<template>
  <div class="polishing-result-page">
    <!-- 顶部栏 -->
    <div class="result-topbar">
      <button class="back-btn" @click="onBack">&larr; 返回</button>
      <div class="topbar-meta">
        <span v-if="modeLabel" class="mode-tag">{{ modeLabel }}</span>
        <TaskStatusBadge v-if="task" :status="task.status" />
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="!task && loading" class="state-center">
      <LoadingSpinner :size="32" label="加载任务状态..." />
    </div>

    <!-- 错误 -->
    <ErrorAlert
      v-else-if="taskError && !task && !isNotFound"
      :message="taskError"
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
      <!-- failed: 错误（独立视图） -->
      <div v-if="displayPhase === 'failed'" class="state-failed">
        <h2 class="state-title">润色失败</h2>
        <ErrorAlert :message="error" :retryable="true" @retry="onRetry" />
      </div>

      <!-- waiting / streaming / completed: 统一容器，标题栏固定 -->
      <div v-else class="state-completed">
        <div class="result-header">
          <div class="header-left">
            <div class="header-spinner" :class="{ visible: displayPhase !== 'completed' }">
              <LoadingSpinner :size="20" label="" />
            </div>
            <h2 class="state-title">
              {{ displayPhase === 'completed' ? '润色完成' : '正在润色中...' }}
            </h2>
            <span v-if="modeLabel" class="mode-tag">{{ modeLabel }}</span>
            <span v-if="currentNode || progress > 0" class="current-node-tag" :class="{ visible: displayPhase !== 'completed' }">
              {{ currentNode }}{{ currentNode && progress > 0 ? ' · ' : '' }}{{ progress > 0 ? Math.round(progress) + '%' : '' }}
            </span>
          </div>
          <div class="header-right">
            <div class="result-actions" :class="{ visible: displayPhase === 'completed' }">
              <div class="view-toggle">
                <button
                  class="toggle-btn"
                  :class="{ active: viewMode === 'result' }"
                  @click="viewMode = 'result'"
                >
                  结果
                </button>
                <button
                  class="toggle-btn"
                  :class="{ active: viewMode === 'compare' }"
                  @click="viewMode = 'compare'"
                >
                  对比
                </button>
                <button
                  v-if="isMode3 && factCheckResult"
                  class="toggle-btn"
                  :class="{ active: viewMode === 'factCheck' }"
                  @click="viewMode = 'factCheck'"
                >
                  核查报告
                </button>
              </div>
              <button class="action-btn" @click="onCopy">
                {{ copied ? '已复制' : '复制全文' }}
              </button>
              <button class="action-btn" :disabled="exporting || viewMode !== 'result'" @click="onExport">
                {{ exporting ? '导出中...' : '导出 PDF' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 模式三：核查摘要（仅 completed 时显示） -->
        <div v-if="displayPhase === 'completed' && isMode3 && accuracyLevel && viewMode !== 'factCheck'" class="fact-check-summary" :class="accuracyClass">
          <div class="summary-header">
            <span class="summary-icon">{{ accuracyLevel === 'high' ? '✓' : accuracyLevel === 'medium' ? '⚠' : '✗' }}</span>
            <span class="summary-title">{{ accuracyDescription }}</span>
          </div>
          <p class="summary-desc">{{ accuracyExplanation }}</p>
        </div>

        <!-- 内容区 -->
        <div v-if="displayPhase === 'completed' && viewMode === 'compare'" class="compare-view">
          <!-- 双栏对比 -->
          <div class="compare-panel">
            <h3 class="compare-label">原文</h3>
            <div class="compare-body">
              <MarkdownRenderer v-if="originalContent" :content="originalContent" />
              <p v-else class="empty-hint">无原文数据</p>
            </div>
          </div>
          <div class="compare-panel">
            <h3 class="compare-label">润色后</h3>
            <div class="compare-body">
              <MarkdownRenderer v-if="result" :content="result" />
              <p v-else class="empty-hint">暂无润色结果</p>
            </div>
          </div>
        </div>

        <div v-else-if="displayPhase === 'completed' && viewMode === 'factCheck' && factCheckResult" class="fact-check-detail">
          <!-- 核查报告详情 -->
          <h3 class="detail-title">事实核查报告</h3>
          <div class="detail-body">
            <MarkdownRenderer :content="factCheckResult" />
          </div>
        </div>

        <div v-else ref="resultBodyRef" class="result-body">
          <!-- 单栏结果 / 流式内容 / 等待 -->
          <MarkdownRenderer v-if="displayContent" :content="displayContent" />
          <span v-if="displayPhase === 'streaming'" class="typing-cursor" />
          <div v-else-if="displayPhase === 'waiting'" class="waiting-hint">
            <LoadingSpinner :size="24" label="" />
          </div>
          <p v-else-if="!displayContent" class="empty-hint">暂无润色结果</p>
        </div>
      </div>
    </template>

    <BackToTop />
  </div>
</template>

<style scoped>
.polishing-result-page {
  max-width: 800px;
  margin: 0 auto;
  padding-top: var(--space-lg);
  padding-bottom: var(--space-xl);
}

/* 顶部栏 */
.result-topbar {
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

.mode-tag {
  padding: 3px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-accent);
  background: var(--color-accent-soft);
  border-radius: 9999px;
}

/* 通用 */
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

.empty-hint {
  font-size: 14px;
  color: var(--color-text-light);
  text-align: center;
  padding: var(--space-lg);
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
  gap: 12px;
}

/* 内容区等待提示 */
.waiting-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl) 0;
}

.view-toggle {
  display: flex;
  background: var(--color-bg);
  border-radius: var(--radius-md);
  padding: 2px;
}

.toggle-btn {
  padding: 5px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.toggle-btn.active {
  background: var(--color-bg-surface);
  color: var(--color-text);
  box-shadow: var(--shadow-sm);
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

.current-node-tag {
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-accent-soft);
  padding: 3px 10px;
  border-radius: var(--radius-md);
}

.result-body {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  background: var(--color-bg-surface);
}

/* 对比视图 */
.compare-view {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
}

.compare-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--color-bg-surface);
}

.compare-label {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 12px 20px;
  margin: 0;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}

.compare-body {
  padding: 20px;
  max-height: 600px;
  overflow-y: auto;
}

/* fact check summary */
.fact-check-summary {
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  border: 1px solid;
}

.accuracy-high {
  background: var(--color-success-bg);
  border-color: var(--color-success);
}

.accuracy-medium {
  background: var(--color-warning-bg);
  border-color: var(--color-warning);
}

.accuracy-low {
  background: var(--color-error-bg);
  border-color: var(--color-error);
}

.summary-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 6px;
}

.summary-icon {
  font-size: 18px;
  font-weight: 700;
}

.accuracy-high .summary-icon {
  color: var(--color-success);
}

.accuracy-medium .summary-icon {
  color: var(--color-warning);
}

.accuracy-low .summary-icon {
  color: var(--color-error);
}

.summary-title {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.summary-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.6;
}

/* fact check detail */
.fact-check-detail {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--color-bg-surface);
}

.detail-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary);
  padding: 12px 20px;
  margin: 0;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}

.detail-body {
  padding: 20px;
  max-height: 400px;
  overflow-y: auto;
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

@media (max-width: 768px) {
  .compare-view {
    grid-template-columns: 1fr;
  }

  .result-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
