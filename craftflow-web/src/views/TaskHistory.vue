<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import TaskStatusBadge from '@/components/common/TaskStatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import { inferTaskType, formatTime, taskRouteName } from '@/utils/taskHelpers'
import type { TaskStatus } from '@/api/types/task'

interface HistoryItem {
  taskId: string
  topic: string
  status: TaskStatus
  createdAt: string
  type: 'creation' | 'polishing'
}

const router = useRouter()
const taskStore = useTaskStore()

const items = ref<HistoryItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const currentPage = computed(() => taskStore.currentPage)
const totalPages = computed(() => taskStore.totalPages)
const total = computed(() => taskStore.taskTotal)

async function loadHistory(page = 1): Promise<void> {
  loading.value = true
  error.value = null
  try {
    await taskStore.fetchTaskList(page)
    items.value = taskStore.taskList.map((t) => {
      const type = inferTaskType(t)
      return {
        taskId: t.task_id,
        topic: t.topic ?? (type === 'polishing' ? '润色任务' : '创作任务'),
        status: t.status,
        createdAt: t.created_at ?? '',
        type,
      }
    })
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : '加载历史记录失败'
  } finally {
    loading.value = false
  }
}

function goToDetail(item: HistoryItem): void {
  router.push({ name: taskRouteName(item.type), params: { taskId: item.taskId } })
}

function onPageChange(page: number): void {
  loadHistory(page)
}

async function onRemove(taskId: string): Promise<void> {
  await taskStore.deleteTask(taskId)
  items.value = items.value.filter((item) => item.taskId !== taskId)
  if (items.value.length === 0 && currentPage.value > 1) {
    loadHistory(currentPage.value - 1)
  }
}

async function onClearAll(): Promise<void> {
  for (const item of items.value) {
    await taskStore.deleteTask(item.taskId)
  }
  items.value = []
  loadHistory(1)
}

onMounted(() => loadHistory())
</script>

<template>
  <div class="history-page">
    <div class="page-header">
      <div class="page-header-left">
        <h1 class="page-title">任务历史</h1>
        <span v-if="total > 0" class="page-count">{{ total }} 条记录</span>
      </div>
      <button
        v-if="items.length > 0"
        class="clear-btn"
        @click="onClearAll"
      >
        清空历史
      </button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading && items.length === 0" class="state-center">
      <LoadingSpinner :size="28" label="加载历史记录..." />
    </div>

    <!-- 错误 -->
    <ErrorAlert
      v-else-if="error"
      :message="error"
      :retryable="true"
      @retry="loadHistory"
    />

    <!-- 空状态 -->
    <div v-else-if="items.length === 0" class="empty-state">
      <p class="empty-text">暂无任务历史</p>
      <button class="empty-action" @click="router.push({ name: 'creation' })">
        发起第一个任务
      </button>
    </div>

    <!-- 列表 -->
    <ul v-else class="history-list">
      <li
        v-for="item in items"
        :key="item.taskId"
        class="history-item"
        @click="goToDetail(item)"
      >
        <div class="item-main">
          <div class="item-top">
            <span class="type-tag" :class="'type-' + item.type">
              {{ item.type === 'creation' ? '创作' : '润色' }}
            </span>
            <TaskStatusBadge :status="item.status" />
          </div>
          <p class="item-topic">{{ item.topic }}</p>
        </div>
        <div class="item-side">
          <span class="item-time">{{ formatTime(item.createdAt) }}</span>
          <button
            class="remove-btn"
            title="移除"
            @click.stop="onRemove(item.taskId)"
          >
            &times;
          </button>
        </div>
      </li>
    </ul>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="pagination">
      <div class="page-controls">
        <button
          class="page-btn"
          :disabled="currentPage <= 1"
          @click="onPageChange(currentPage - 1)"
        >
          上一页
        </button>
        <span class="page-number">{{ currentPage }} / {{ totalPages }}</span>
        <button
          class="page-btn"
          :disabled="currentPage >= totalPages"
          @click="onPageChange(currentPage + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-page {
  max-width: 720px;
  margin: 0 auto;
  padding-top: var(--space-lg);
  padding-bottom: var(--space-xl);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-lg);
}

.page-header-left {
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
}

.page-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.page-count {
  font-size: 13px;
  color: var(--color-text-muted);
}

.clear-btn {
  padding: 6px 14px;
  font-size: 13px;
  color: #b91c1c;
  background: transparent;
  border: 1px solid #fecaca;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.clear-btn:hover {
  background: #fef2f2;
}

/* 通用 */
.state-center {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-md);
  padding: 48px 0;
}

.empty-text {
  font-size: 15px;
  color: var(--color-text-muted);
  margin: 0;
}

.empty-action {
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  background: var(--color-accent);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.empty-action:hover {
  background: var(--color-accent-hover);
}

/* 列表 */
.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: 14px 18px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.history-item:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-sm);
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-top {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 6px;
}

.type-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 9999px;
}

.type-creation {
  color: var(--color-accent);
  background: var(--color-accent-soft);
}

.type-polishing {
  color: #7c3aed;
  background: #ede9fe;
}

.item-topic {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-side {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.item-time {
  font-size: 13px;
  color: var(--color-text-light);
}

.remove-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--color-text-light);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.remove-btn:hover {
  color: #b91c1c;
  background: #fef2f2;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: var(--space-lg);
  padding: var(--space-md) 0;
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-btn {
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.page-btn:hover:not(:disabled) {
  border-color: var(--color-text-muted);
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-number {
  font-size: 13px;
  color: var(--color-text-muted);
  min-width: 60px;
  text-align: center;
}

@media (max-width: 768px) {
  .history-item {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-sm);
  }

  .item-side {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
