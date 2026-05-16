<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useNavigationStore } from '@/stores/navigation'
import TaskStatusBadge from '@/components/common/TaskStatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import ConfirmDeleteModal from '@/components/common/ConfirmDeleteModal.vue'
import { deleteTasksByStatus } from '@/api/tasks'
import { inferTaskType, formatTime, taskRouteName } from '@/utils/taskHelpers'
import type { TaskStatus, TaskStatusResponse } from '@/api/types/task'

interface HistoryItem {
  taskId: string
  topic: string
  status: TaskStatus
  createdAt: string
  type: 'creation' | 'polishing'
}

type TabType = 'running' | 'history'

const router = useRouter()
const taskStore = useTaskStore()
const navStore = useNavigationStore()

const activeTab = ref<TabType>('history')
const deleting = ref(false)

// 删除确认弹窗状态
const deleteModalVisible = ref(false)
const deleteModalLoading = ref(false)
const deleteTarget = ref<{ type: 'single' | 'clearAll'; taskId?: string; topic?: string }>({ type: 'single' })

// 定时刷新间隔（30 秒）
const REFRESH_INTERVAL = 30_000
let refreshTimer: ReturnType<typeof setInterval> | null = null

/** 将 TaskStatusResponse 映射为 HistoryItem */
function toHistoryItem(t: TaskStatusResponse): HistoryItem {
  const type = inferTaskType(t)
  return {
    taskId: t.task_id,
    topic: t.topic ?? (type === 'polishing' ? '润色任务' : '创作任务'),
    status: t.status,
    createdAt: t.created_at ?? '',
    type,
  }
}

/** 当前 Tab 的列表数据 */
const items = computed<HistoryItem[]>(() => {
  if (activeTab.value === 'running') {
    return taskStore.runningItems.map(toHistoryItem)
  }
  return taskStore.taskList.map(toHistoryItem)
})

/** 当前 Tab 的当前页 */
const currentPage = computed(() =>
  activeTab.value === 'running' ? taskStore.runningCurrentPage : taskStore.currentPage,
)

/** 当前 Tab 的总页数 */
const totalPages = computed(() =>
  activeTab.value === 'running' ? taskStore.runningTotalPages : taskStore.totalPages,
)

/** 当前 Tab 的总数 */
const total = computed(() =>
  activeTab.value === 'running' ? taskStore.runningTotal : taskStore.listTotal,
)

/** 切换 Tab */
function switchTab(tab: TabType): void {
  activeTab.value = tab
}

async function loadList(page?: number): Promise<void> {
  await taskStore.fetchTaskList(page, activeTab.value)
}

function goToDetail(item: HistoryItem): void {
  navStore.setDetailSource('history')
  router.push({ name: taskRouteName(item.type), params: { taskId: item.taskId } })
}

function onPageChange(page: number): void {
  loadList(page)
}

function promptRemove(taskId: string, topic: string): void {
  deleteTarget.value = { type: 'single', taskId, topic }
  deleteModalVisible.value = true
}

function promptClearAll(): void {
  deleteTarget.value = { type: 'clearAll' }
  deleteModalVisible.value = true
}

async function confirmDelete(): Promise<void> {
  deleteModalLoading.value = true
  deleting.value = true
  try {
    if (deleteTarget.value.type === 'single' && deleteTarget.value.taskId) {
      await taskStore.deleteTask(deleteTarget.value.taskId)
      if (items.value.length === 0 && currentPage.value > 1) {
        await loadList(currentPage.value - 1)
      }
    } else if (deleteTarget.value.type === 'clearAll') {
      await deleteTasksByStatus(['completed', 'failed'])
      await loadList(1)
    }
  } catch {
    if (deleteTarget.value.type === 'clearAll') {
      await loadList(1)
    }
  } finally {
    deleteModalLoading.value = false
    deleting.value = false
    deleteModalVisible.value = false
  }
}

onMounted(() => {
  loadList()
  // 定时刷新，确保任务状态实时更新
  refreshTimer = setInterval(() => {
    loadList()
  }, REFRESH_INTERVAL)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<template>
  <div class="history-page">
    <div class="page-header">
      <div class="page-header-left">
        <h1 class="page-title">任务历史</h1>
      </div>
      <button
        v-if="activeTab === 'history' && items.length > 0"
        class="clear-btn"
        :disabled="deleting"
        @click="promptClearAll"
      >
        清空历史
      </button>
    </div>

    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'history' }"
        @click="switchTab('history')"
      >
        历史记录
        <span class="tab-badge">{{ taskStore.listTotal }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'running' }"
        @click="switchTab('running')"
      >
        运行中
        <span class="tab-badge">{{ taskStore.runningTotal }}</span>
      </button>
    </div>

    <!-- 内容区（列表 + 分页） -->
    <div class="content-area">
      <!-- 加载中 -->
      <div v-if="taskStore.loading && items.length === 0" class="state-center">
        <LoadingSpinner :size="28" label="加载中..." />
      </div>

      <!-- 错误 -->
      <ErrorAlert
        v-else-if="taskStore.error"
        :message="taskStore.error"
        :retryable="true"
        @retry="loadList"
      />

      <!-- 空状态 -->
      <div v-else-if="items.length === 0" class="empty-state">
        <p class="empty-text">
          {{ activeTab === 'running' ? '暂无运行中的任务' : '暂无历史记录' }}
        </p>
        <button
          v-if="activeTab === 'history'"
          class="empty-action"
          @click="router.push({ name: 'creation' })"
        >
          发起第一个任务
        </button>
      </div>

      <!-- 列表 -->
      <template v-else>
        <ul class="history-list">
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
                v-if="activeTab === 'history'"
                class="remove-btn"
                title="移除"
                :disabled="deleting"
                @click.stop="promptRemove(item.taskId, item.topic)"
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
      </template>
    </div>

    <ConfirmDeleteModal
      v-model:visible="deleteModalVisible"
      :title="deleteTarget.type === 'clearAll' ? '清空历史' : '删除任务'"
      :message="deleteTarget.type === 'clearAll'
        ? `确定清空全部 ${total} 条历史记录吗？此操作不可恢复。`
        : `确定删除任务「${deleteTarget.topic}」吗？此操作不可恢复。`"
      :confirm-text="deleteTarget.type === 'clearAll' ? '清空' : '删除'"
      :loading="deleteModalLoading"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.history-page {
  max-width: 720px;
  width: 100%;
  margin: 0 auto;
  height: calc(100vh - var(--space-xl) * 2);
  display: grid;
  grid-template-rows: auto auto 1fr;
  padding-top: var(--space-lg);
  padding-bottom: var(--space-xl);
}

.content-area {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
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
  color: var(--color-error);
  background: transparent;
  border: 1px solid var(--color-error);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  opacity: 0.8;
}

.clear-btn:hover {
  opacity: 1;
  background: var(--color-error-bg);
}

/* Tab 切换 */
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: var(--space-lg);
  border-bottom: 1px solid var(--color-border);
}

.tab-btn {
  position: relative;
  width: 140px;
  padding: 10px 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.tab-btn:hover {
  color: var(--color-text-secondary);
}

.tab-btn.active {
  color: var(--color-accent);
  border-bottom-color: var(--color-accent);
}

.tab-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  min-width: 20px;
  text-align: center;
  border-radius: 9999px;
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

.tab-btn:not(.active) .tab-badge {
  background: var(--color-bg-surface);
  color: var(--color-text-muted);
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
  flex: 1;
  overflow-y: auto;
  scrollbar-width: none;
}

.history-list::-webkit-scrollbar {
  display: none;
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
  color: var(--color-info);
  background: var(--color-info-bg);
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
  color: var(--color-error);
  background: var(--color-error-bg);
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
