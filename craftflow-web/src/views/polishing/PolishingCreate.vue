<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTaskLifecycle } from '@/composables/useTaskLifecycle'
import { useSettingsStore } from '@/stores/settings'
import { POLISHING_MODE_META } from '@/api/types/polishing'
import type { PolishingMode } from '@/api/types/polishing'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const { submitPolishing, submitting, submitError } = useTaskLifecycle()
const settingsStore = useSettingsStore()

const content = ref('')
const selectedMode = ref<PolishingMode>(1)
const noLlmError = ref(false)
const noLlmErrorMsg = ref('尚未配置 LLM 模型，请先添加至少一个配置')

const CONTENT_MIN = 10
const CONTENT_MAX = 50_000

const contentLength = computed(() => content.value.length)

const contentError = computed<string | null>(() => {
  const len = contentLength.value
  if (len === 0) return null
  if (len < CONTENT_MIN) return `内容至少需要 ${CONTENT_MIN} 个字符`
  if (len > CONTENT_MAX) return `内容不能超过 ${CONTENT_MAX} 个字符`
  return null
})

const canSubmit = computed(() => {
  const len = contentLength.value
  return len >= CONTENT_MIN && len <= CONTENT_MAX && !submitting.value
})

function selectMode(mode: number): void {
  selectedMode.value = mode as PolishingMode
}

async function onSubmit(): Promise<void> {
  if (!canSubmit.value) return

  const hasProfiles = await settingsStore.checkProfiles()
  if (!hasProfiles) {
    noLlmErrorMsg.value = '尚未配置 LLM 模型，请先添加至少一个配置'
    noLlmError.value = true
    return
  }
  const hasDefault = await settingsStore.checkHasDefault()
  if (!hasDefault) {
    noLlmErrorMsg.value = '未设置默认 LLM 配置，请在设置页面将其中一个配置设为默认'
    noLlmError.value = true
    return
  }
  noLlmError.value = false
  await submitPolishing(content.value, selectedMode.value)
}

function goToLlmSettings(): void {
  settingsStore.openSettingsModal('llm')
}

function onRetry(): void {
  onSubmit()
}
</script>

<template>
  <div class="polishing-create-page">
    <div class="page-header">
      <h1 class="page-title">润色文章</h1>
      <p class="page-subtitle">粘贴你的文章，选择润色模式，AI 将为你优化内容</p>
    </div>

    <form class="create-form" @submit.prevent="onSubmit">
      <!-- 内容输入 -->
      <div class="form-group">
        <label class="form-label" for="content">
          文章内容 <span class="required">*</span>
        </label>
        <textarea
          id="content"
          v-model="content"
          class="form-textarea"
          :class="{ 'input-error': contentError }"
          placeholder="在此粘贴你的 Markdown 文章..."
          :rows="12"
          :maxlength="CONTENT_MAX + 100"
          :disabled="submitting"
        />
        <div class="form-meta">
          <span v-if="contentError" class="error-text">{{ contentError }}</span>
          <span class="char-count" :class="{ 'count-over': contentLength > CONTENT_MAX }">
            {{ contentLength.toLocaleString() }}/{{ CONTENT_MAX.toLocaleString() }}
          </span>
        </div>
      </div>

      <!-- 模式选择 -->
      <div class="form-group">
        <label class="form-label">润色模式</label>
        <div class="mode-cards">
          <button
            v-for="(meta, mode) in POLISHING_MODE_META"
            :key="mode"
            type="button"
            class="mode-card"
            :class="{ 'mode-selected': selectedMode === Number(mode) }"
            :disabled="submitting"
            @click="selectMode(Number(mode))"
          >
            <div class="mode-badge">{{ mode }}</div>
            <div class="mode-info">
              <div class="mode-header">
                <p class="mode-label">{{ meta.label }}</p>
                <span v-if="meta.extra" class="mode-extra">{{ meta.extra }}</span>
              </div>
              <p class="mode-desc">{{ meta.description }}</p>
            </div>
          </button>
        </div>
      </div>

      <div v-if="noLlmError" class="llm-warning">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span class="llm-warning-text">{{ noLlmErrorMsg }}</span>
        <button type="button" class="llm-warning-btn" @click="goToLlmSettings">
          前往设置
        </button>
      </div>

      <ErrorAlert
        v-if="submitError"
        :message="submitError"
        :retryable="true"
        @retry="onRetry"
      />

      <button
        type="submit"
        class="submit-btn"
        :disabled="!canSubmit"
      >
        <LoadingSpinner v-if="submitting" :size="18" label="" />
        <span v-if="submitting">提交中...</span>
        <span v-else>开始润色</span>
      </button>
    </form>
  </div>
</template>

<style scoped>
.polishing-create-page {
  max-width: 720px;
  margin: 0 auto;
  padding-top: var(--space-lg);
  padding-bottom: var(--space-xl);
}

.page-header {
  margin-bottom: var(--space-xl);
}

.page-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 var(--space-sm);
}

.page-subtitle {
  font-size: 15px;
  color: var(--color-text-muted);
  margin: 0;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.form-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.required {
  color: var(--color-error);
}

.form-textarea {
  width: 100%;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  box-sizing: border-box;
  resize: vertical;
  min-height: 200px;
  font-family: var(--font-mono);
}

.form-textarea:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}

.form-textarea.input-error {
  border-color: var(--color-error);
}

.form-textarea:disabled {
  background: var(--color-bg);
  cursor: not-allowed;
}

.form-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 20px;
}

.error-text {
  font-size: 13px;
  color: var(--color-error);
}

.char-count {
  font-size: 12px;
  color: var(--color-text-light);
  margin-left: auto;
}

.char-count.count-over {
  color: var(--color-error);
  font-weight: 500;
}

/* 模式卡片 */
.mode-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mode-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: var(--color-bg-surface);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  text-align: left;
  transition: all var(--transition-fast);
}

.mode-card:hover:not(:disabled) {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-sm);
}

.mode-card.mode-selected {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.mode-card:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mode-badge {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
}

.mode-selected .mode-badge {
  background: var(--color-accent);
  color: #fff;
}

.mode-info {
  flex: 1;
  min-width: 0;
}

.mode-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 2px;
}

.mode-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.mode-extra {
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-bg);
  padding: 1px 8px;
  border-radius: 9999px;
  white-space: nowrap;
}

.mode-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  margin: 0;
}

/* 提交按钮 */
.submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: 12px 28px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: var(--color-accent);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), opacity var(--transition-fast);
  align-self: flex-start;
}

.submit-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* LLM 未配置警告 */
.llm-warning {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 12px 16px;
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-md);
  color: var(--color-warning);
}

.llm-warning-text {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
}

.llm-warning-btn {
  flex-shrink: 0;
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  transition: background var(--transition-fast);
}

.llm-warning-btn:hover {
  background: var(--color-accent-hover);
}

@media (max-width: 768px) {
  .page-title {
    font-size: 24px;
  }
}
</style>
