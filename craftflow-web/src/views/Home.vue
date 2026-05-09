<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import TaskStatusBadge from '@/components/common/TaskStatusBadge.vue'
import { inferTaskType, formatTime, taskRouteName } from '@/utils/taskHelpers'
import type { TaskStatus } from '@/api/types/task'

interface RecentTask {
  taskId: string
  topic: string
  status: TaskStatus
  type: 'creation' | 'polishing'
  createdAt: string
}

const router = useRouter()
const taskStore = useTaskStore()

const recentTasks = ref<RecentTask[]>([])

async function loadRecent(): Promise<void> {
  await taskStore.fetchTaskList()
  recentTasks.value = taskStore.taskList.slice(0, 5).map((t: import('@/api/types/task').TaskStatusResponse) => {
    const type = inferTaskType(t)
    return {
      taskId: t.task_id,
      topic: t.topic ?? (type === 'polishing' ? '润色任务' : '创作任务'),
      status: t.status,
      type,
      createdAt: t.created_at ?? '',
    }
  })
}

function goToTask(item: RecentTask): void {
  router.push({ name: taskRouteName(item.type), params: { taskId: item.taskId } })
}

onMounted(loadRecent)
</script>

<template>
  <div class="home-page">
    <!-- Hero -->
    <div class="hero">
      <h1 class="hero-title">CraftFlow</h1>
      <div class="hero-rule" />
      <p class="hero-subtitle">AI 驱动的智能长文创作与审校平台</p>
    </div>

    <!-- 入口卡片 -->
    <div class="action-cards">
      <button class="action-card" @click="router.push({ name: 'creation' })">
        <div class="action-icon action-icon-creation">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
        </div>
        <div class="action-info">
          <h2 class="action-title">开始创作</h2>
          <p class="action-desc">输入主题，AI 自动生成大纲并撰写长文</p>
        </div>
        <span class="action-arrow">&rarr;</span>
      </button>

      <button class="action-card" @click="router.push({ name: 'polishing' })">
        <div class="action-icon action-icon-polishing">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3z" />
          </svg>
        </div>
        <div class="action-info">
          <h2 class="action-title">润色文章</h2>
          <p class="action-desc">粘贴文章，选择模式，AI 为你优化内容</p>
        </div>
        <span class="action-arrow">&rarr;</span>
      </button>
    </div>

    <!-- 最近任务 -->
    <div v-if="recentTasks.length > 0" class="recent-section">
      <div class="recent-header">
        <h3 class="recent-title">最近任务</h3>
        <button
          class="view-all-btn"
          @click="router.push({ name: 'history' })"
        >
          查看全部
        </button>
      </div>
      <ul class="recent-list">
        <li
          v-for="item in recentTasks"
          :key="item.taskId"
          class="recent-item"
          @click="goToTask(item)"
        >
          <span class="type-tag" :class="'type-' + item.type">
            {{ item.type === 'creation' ? '创作' : '润色' }}
          </span>
          <span class="recent-topic">{{ item.topic }}</span>
          <TaskStatusBadge :status="item.status" />
          <span class="recent-time">{{ formatTime(item.createdAt) }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  max-width: 640px;
  margin: 0 auto;
  padding-top: var(--space-2xl);
  padding-bottom: var(--space-xl);
}

/* Hero */
.hero {
  text-align: center;
  margin-bottom: var(--space-2xl);
}

.hero-title {
  font-family: var(--font-display);
  font-size: 42px;
  font-weight: 700;
  font-style: italic;
  color: var(--color-text);
  margin: 0 0 12px;
  letter-spacing: -0.02em;
}

.hero-rule {
  width: 48px;
  height: 2px;
  background: var(--color-accent);
  margin: 0 auto 16px;
}

.hero-subtitle {
  font-size: 16px;
  color: var(--color-text-muted);
  margin: 0;
  letter-spacing: 0.01em;
}

/* 入口卡片 */
.action-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  margin-bottom: var(--space-2xl);
}

.action-card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: 20px 24px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.action-card:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-md);
}

.action-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
}

.action-icon-creation {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

.action-icon-polishing {
  background: #f0ead6;
  color: #92730a;
}

.action-info {
  flex: 1;
  min-width: 0;
}

.action-title {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 3px;
}

.action-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  margin: 0;
}

.action-arrow {
  flex-shrink: 0;
  font-size: 18px;
  color: var(--color-text-light);
  transition: color var(--transition-fast), transform var(--transition-fast);
}

.action-card:hover .action-arrow {
  color: var(--color-accent);
  transform: translateX(2px);
}

/* 最近任务 */
.recent-section {
  border-top: 1px solid var(--color-rule);
  padding-top: var(--space-lg);
}

.recent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}

.recent-title {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.view-all-btn {
  font-size: 13px;
  color: var(--color-accent);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  transition: opacity var(--transition-fast);
}

.view-all-btn:hover {
  opacity: 0.7;
}

.recent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.recent-item:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-sm);
}

.type-tag {
  flex-shrink: 0;
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

.recent-topic {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-time {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-text-light);
}

@media (max-width: 768px) {
  .home-page {
    padding-top: var(--space-lg);
  }

  .hero-title {
    font-size: 32px;
  }

  .action-card {
    padding: 16px;
  }

  .recent-item {
    flex-wrap: wrap;
    gap: 6px;
  }

  .recent-topic {
    order: 3;
    width: 100%;
  }
}
</style>
