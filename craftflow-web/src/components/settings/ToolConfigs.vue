<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const store = useSettingsStore()

const tavilyKey = ref('')
const e2bKey = ref('')
const saving = ref(false)
const saveSuccess = ref(false)

onMounted(async () => {
  await store.fetchToolConfigs()
  // 不回显实际值，仅标记是否已配置
  tavilyKey.value = ''
  e2bKey.value = ''
})

function placeholderText(masked: string): string {
  return masked ? '已配置，留空则不修改' : '未配置'
}

async function handleSave(): Promise<void> {
  const data: Record<string, string> = {}
  if (tavilyKey.value.trim()) data.tavily_api_key = tavilyKey.value.trim()
  if (e2bKey.value.trim()) data.e2b_api_key = e2bKey.value.trim()

  if (Object.keys(data).length === 0) return

  saving.value = true
  saveSuccess.value = false
  try {
    await store.saveToolConfigs(data)
    tavilyKey.value = ''
    e2bKey.value = ''
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 2000)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="tool-configs">
    <div class="tool-cards">
      <div class="tool-card">
        <div class="tool-info">
          <span class="tool-name">Tavily Search</span>
          <span class="tool-desc">用于联网搜索（创作任务的信息检索）</span>
        </div>
        <input
          v-model="tavilyKey"
          type="password"
          class="tool-input"
          :placeholder="placeholderText(store.toolConfigs.tavily_api_key)"
          autocomplete="off"
        />
      </div>

      <div class="tool-card">
        <div class="tool-info">
          <span class="tool-name">E2B Code Sandbox</span>
          <span class="tool-desc">用于代码沙箱（编程类任务的代码执行）</span>
        </div>
        <input
          v-model="e2bKey"
          type="password"
          class="tool-input"
          :placeholder="placeholderText(store.toolConfigs.e2b_api_key)"
          autocomplete="off"
        />
      </div>
    </div>

    <p class="tool-hint">配置后相关工具自动可用，留空则跳过。留空表示不修改已有配置。</p>

    <div class="tool-actions">
      <Transition name="fade">
        <span v-if="saveSuccess" class="save-success">已保存</span>
      </Transition>
      <button
        class="btn-save"
        :disabled="saving || (!tavilyKey.trim() && !e2bKey.trim())"
        @click="handleSave"
      >
        {{ saving ? '保存中...' : '保存' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.tool-configs {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.tool-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.tool-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
}

.tool-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
}

.tool-desc {
  font-size: 12px;
  color: var(--color-text-muted);
}

.tool-input {
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 14px;
  font-family: var(--font-mono);
  transition: border-color var(--transition-fast);
}

.tool-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.tool-input::placeholder {
  color: var(--color-text-muted);
  font-family: inherit;
}

.tool-hint {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: calc(-1 * var(--space-sm));
}

.tool-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-md);
}

.save-success {
  font-size: 13px;
  color: var(--color-success, #22c55e);
  font-weight: 500;
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 200ms ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
