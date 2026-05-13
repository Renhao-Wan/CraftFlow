<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const store = useSettingsStore()

// 创作参数
const maxSections = ref(5)
const maxWriters = ref(3)
// 审校参数
const maxDebateIterations = ref(3)
const editorPassScore = ref(90)
// 超时参数
const taskTimeout = ref(3600)
const toolCallTimeout = ref(30)

const saving = ref(false)

onMounted(async () => {
  await store.fetchWritingParams()
  const p = store.writingParams
  maxSections.value = p.max_outline_sections
  maxWriters.value = p.max_concurrent_writers
  maxDebateIterations.value = p.max_debate_iterations
  editorPassScore.value = p.editor_pass_score
  taskTimeout.value = p.task_timeout
  toolCallTimeout.value = p.tool_call_timeout
})

async function handleSave(): Promise<void> {
  saving.value = true
  try {
    await store.saveWritingParams({
      max_outline_sections: maxSections.value,
      max_concurrent_writers: maxWriters.value,
      max_debate_iterations: maxDebateIterations.value,
      editor_pass_score: editorPassScore.value,
      task_timeout: taskTimeout.value,
      tool_call_timeout: toolCallTimeout.value,
    })
  } finally {
    saving.value = false
  }
}

function formatTimeout(seconds: number): string {
  if (seconds >= 3600) return `${(seconds / 3600).toFixed(0)} 小时`
  if (seconds >= 60) return `${(seconds / 60).toFixed(0)} 分钟`
  return `${seconds} 秒`
}
</script>

<template>
  <div class="writing-params">
    <!-- 创作参数 -->
    <h4 class="group-title">创作参数</h4>
    <div class="param-cards">
      <div class="param-card">
        <div class="param-info">
          <span class="param-label">大纲最大章节数</span>
          <span class="param-desc">创作任务生成的大纲中最多包含的章节数量</span>
        </div>
        <div class="param-control">
          <input
            v-model.number="maxSections"
            type="number"
            class="param-input"
            min="1"
            max="20"
          />
          <span class="param-range-hint">1-20</span>
        </div>
      </div>

      <div class="param-card">
        <div class="param-info">
          <span class="param-label">最大并发写作者</span>
          <span class="param-desc">同时撰写章节数量，越大速度越快但 LLM 调用成本越高</span>
        </div>
        <div class="param-control">
          <input
            v-model.number="maxWriters"
            type="number"
            class="param-input"
            min="1"
            max="10"
          />
          <span class="param-range-hint">1-10</span>
        </div>
      </div>
    </div>

    <!-- 审校参数 -->
    <h4 class="group-title">审校参数</h4>
    <div class="param-cards">
      <div class="param-card">
        <div class="param-info">
          <span class="param-label">对抗循环最大迭代</span>
          <span class="param-desc">专家对抗审查（Debate）中作者-编辑博弈的最大轮次</span>
        </div>
        <div class="param-control">
          <input
            v-model.number="maxDebateIterations"
            type="number"
            class="param-input"
            min="1"
            max="10"
          />
          <span class="param-range-hint">1-10</span>
        </div>
      </div>

      <div class="param-card">
        <div class="param-info">
          <span class="param-label">主编通过分数</span>
          <span class="param-desc">编辑评分达到此分数时提前结束对抗循环（满分 100）</span>
        </div>
        <div class="param-control">
          <input
            v-model.number="editorPassScore"
            type="number"
            class="param-input"
            min="0"
            max="100"
          />
          <span class="param-range-hint">0-100</span>
        </div>
      </div>
    </div>

    <!-- 超时参数 -->
    <h4 class="group-title">超时参数</h4>
    <div class="param-cards">
      <div class="param-card">
        <div class="param-info">
          <span class="param-label">任务超时时间</span>
          <span class="param-desc">单个创作/润色任务的最大执行时间，超时后自动标记为失败</span>
        </div>
        <div class="param-control">
          <input
            v-model.number="taskTimeout"
            type="number"
            class="param-input"
            min="60"
            max="86400"
          />
          <span class="param-range-hint">{{ formatTimeout(taskTimeout) }}</span>
        </div>
      </div>

      <div class="param-card">
        <div class="param-info">
          <span class="param-label">工具调用超时</span>
          <span class="param-desc">单次外部工具调用（搜索、代码沙箱）的最大等待时间</span>
        </div>
        <div class="param-control">
          <input
            v-model.number="toolCallTimeout"
            type="number"
            class="param-input"
            min="5"
            max="300"
          />
          <span class="param-range-hint">{{ formatTimeout(toolCallTimeout) }}</span>
        </div>
      </div>
    </div>

    <div class="param-actions">
      <button class="btn-save" :disabled="saving" @click="handleSave">
        {{ saving ? '保存中...' : '保存参数' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.writing-params {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.group-title {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: calc(-1 * var(--space-sm));
}

.param-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.param-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
}

.param-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
}

.param-desc {
  font-size: 12px;
  color: var(--color-text-muted);
  max-width: 320px;
}

.param-control {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.param-input {
  width: 80px;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  transition: border-color var(--transition-fast);
}

.param-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.param-range-hint {
  font-size: 11px;
  color: var(--color-text-muted);
}

.param-actions {
  margin-top: var(--space-sm);
}

.btn-save {
  padding: var(--space-sm) var(--space-xl);
  border-radius: var(--radius-md);
  background: var(--color-accent);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  transition: background var(--transition-fast);
}

.btn-save:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
