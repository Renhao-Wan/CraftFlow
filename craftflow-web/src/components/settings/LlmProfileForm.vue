<script setup lang="ts">
import { ref, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import type { LlmProfile, LlmProfileRequest } from '@/api/types/settings'

const props = defineProps<{
  visible: boolean
  profile?: LlmProfile | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const store = useSettingsStore()

const form = ref<LlmProfileRequest>({
  name: '',
  api_key: '',
  api_base: '',
  model: '',
  temperature: 0.7,
  is_default: false,
})

const submitting = ref(false)
const formError = ref<string | null>(null)

watch(
  () => props.visible,
  (val) => {
    if (val && props.profile) {
      form.value = {
        name: props.profile.name,
        api_key: '', // 不回显 API Key
        api_base: props.profile.api_base,
        model: props.profile.model,
        temperature: props.profile.temperature,
        is_default: props.profile.is_default,
      }
    } else if (val) {
      form.value = {
        name: '',
        api_key: '',
        api_base: '',
        model: '',
        temperature: 0.7,
        is_default: false,
      }
    }
    formError.value = null
  },
)

// 用户修改名称时清除错误（允许重试）
watch(
  () => form.value.name,
  () => {
    formError.value = null
  },
)

async function handleSubmit(): Promise<void> {
  submitting.value = true
  try {
    if (props.profile) {
      await store.editProfile(props.profile.id, form.value)
    } else {
      await store.addProfile(form.value)
    }
    formError.value = null
    emit('saved')
    emit('close')
  } catch (e) {
    formError.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="emit('close')">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ profile ? '编辑 LLM 配置' : '新增 LLM 配置' }}</h3>
          <button class="btn-close" @click="emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <form class="modal-body" @submit.prevent="handleSubmit">
          <div class="form-group">
            <label class="form-label">配置名称 *</label>
            <input
              v-model="form.name"
              type="text"
              class="form-input"
              placeholder="如：GPT-4、DeepSeek"
              required
            />
          </div>

          <div class="form-group">
            <label class="form-label">API Key *</label>
            <input
              v-model="form.api_key"
              type="password"
              class="form-input"
              :placeholder="profile ? '留空则不修改' : 'sk-...'"
              :required="!profile"
            />
          </div>

          <div class="form-group">
            <label class="form-label">API Base URL</label>
            <input
              v-model="form.api_base"
              type="text"
              class="form-input"
              placeholder="https://api.openai.com/v1"
            />
            <span class="form-hint">需为 OpenAI 兼容格式</span>
          </div>

          <div class="form-group">
            <label class="form-label">模型名称 *</label>
            <input
              v-model="form.model"
              type="text"
              class="form-input"
              placeholder="gpt-4、deepseek-chat"
              required
            />
          </div>

          <div class="form-group">
            <label class="form-label">温度参数 ({{ form.temperature }})</label>
            <input
              v-model.number="form.temperature"
              type="range"
              class="form-range"
              min="0"
              max="2"
              step="0.1"
            />
            <div class="range-labels">
              <span>精确</span>
              <span>随机</span>
            </div>
          </div>

          <div class="form-group form-checkbox">
            <label class="checkbox-label">
              <input v-model="form.is_default" type="checkbox" />
              <span>设为默认配置</span>
            </label>
          </div>

          <div v-if="formError" class="form-error">{{ formError }}</div>

          <div class="modal-footer">
            <button type="button" class="btn-cancel" @click="emit('close')">
              取消
            </button>
            <button type="submit" class="btn-submit" :disabled="submitting || !!formError">
              {{ submitting ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2100;
  animation: fadeIn 150ms ease;
}

.modal-content {
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  background: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  scrollbar-width: none;
}

.modal-content::-webkit-scrollbar {
  display: none;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-lg) var(--space-lg) var(--space-md);
}

.modal-header h3 {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: all var(--transition-fast);
}

.btn-close:hover {
  background: var(--color-bg-surface);
  color: var(--color-text);
}

.modal-body {
  padding: 0 var(--space-lg) var(--space-lg);
}

.form-group {
  margin-bottom: var(--space-md);
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-xs);
}

.form-input {
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 14px;
  transition: border-color var(--transition-fast);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.form-hint {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.form-error {
  padding: var(--space-sm) var(--space-md);
  background: var(--color-error-bg, #fef2f2);
  border: 1px solid var(--color-error, #ef4444);
  border-radius: var(--radius-sm);
  color: var(--color-error, #ef4444);
  font-size: 13px;
  margin-top: var(--space-sm);
}

.form-range {
  width: 100%;
  accent-color: var(--color-accent);
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: var(--space-xs);
}

.form-checkbox {
  margin-top: var(--space-md);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 14px;
  color: var(--color-text);
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  accent-color: var(--color-accent);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  margin-top: var(--space-lg);
}

.btn-cancel {
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-surface);
  color: var(--color-text-secondary);
  font-size: 14px;
  transition: all var(--transition-fast);
}

.btn-cancel:hover {
  border-color: var(--color-text-muted);
}

.btn-submit {
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-md);
  background: var(--color-accent);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  transition: background var(--transition-fast);
}

.btn-submit:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.btn-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
