<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const store = useSettingsStore()

const maxSections = ref(5)
const maxWriters = ref(3)
const saving = ref(false)

onMounted(async () => {
  await store.fetchWritingParams()
  maxSections.value = store.writingParams.max_outline_sections
  maxWriters.value = store.writingParams.max_concurrent_writers
})

async function handleSave(): Promise<void> {
  saving.value = true
  try {
    await store.saveWritingParams({
      max_outline_sections: maxSections.value,
      max_concurrent_writers: maxWriters.value,
    })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="writing-params">
    <h3 class="section-title">写作参数</h3>

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

    <div class="param-actions">
      <button class="btn-save" :disabled="saving" @click="handleSave">
        {{ saving ? '保存中...' : '保存参数' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.writing-params {
  margin-bottom: var(--space-xl);
}

.section-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-md);
}

.param-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
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
}

.param-control {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
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
  margin-top: var(--space-lg);
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
