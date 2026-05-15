<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

interface Props {
  visible: boolean
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '确认删除',
  confirmText: '删除',
  cancelText: '取消',
  loading: false,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
  'update:visible': [value: boolean]
}>()

function handleConfirm(): void {
  emit('confirm')
}

function handleCancel(): void {
  emit('cancel')
  emit('update:visible', false)
}

function handleOverlayClick(): void {
  if (!props.loading) {
    handleCancel()
  }
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.visible && !props.loading) {
    handleCancel()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="confirm-modal">
      <div v-if="visible" class="confirm-overlay" @click.self="handleOverlayClick">
        <div class="confirm-dialog" role="dialog" aria-modal="true">
          <div class="confirm-header">
            <div class="confirm-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h3 class="confirm-title">{{ title }}</h3>
          </div>
          <p class="confirm-message">{{ message }}</p>
          <div class="confirm-actions">
            <button
              class="btn-confirm-cancel"
              :disabled="loading"
              @click="handleCancel"
            >
              {{ cancelText }}
            </button>
            <button
              class="btn-confirm-delete"
              :disabled="loading"
              @click="handleConfirm"
            >
              <span v-if="loading" class="btn-spinner" />
              {{ loading ? '删除中...' : confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2200;
}

.confirm-dialog {
  width: 400px;
  max-width: 90vw;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-lg);
}

.confirm-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
}

.confirm-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-error-bg);
  color: var(--color-error);
  flex-shrink: 0;
}

.confirm-title {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.confirm-message {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-lg);
  padding-left: calc(36px + var(--space-sm));
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}

.btn-confirm-cancel,
.btn-confirm-delete {
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.btn-confirm-cancel {
  color: var(--color-text-secondary);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
}

.btn-confirm-cancel:hover:not(:disabled) {
  border-color: var(--color-text-muted);
}

.btn-confirm-delete {
  color: #fff;
  background: var(--color-error);
  border: 1px solid var(--color-error);
}

.btn-confirm-delete:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-confirm-cancel:disabled,
.btn-confirm-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: confirm-spin 0.6s linear infinite;
}

@keyframes confirm-spin {
  to { transform: rotate(360deg); }
}

/* 进出动画 */
.confirm-modal-enter-active {
  transition: opacity 0.2s ease;
}

.confirm-modal-leave-active {
  transition: opacity 0.15s ease;
}

.confirm-modal-enter-from,
.confirm-modal-leave-to {
  opacity: 0;
}

.confirm-modal-enter-active .confirm-dialog {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.confirm-modal-leave-active .confirm-dialog {
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.confirm-modal-enter-from .confirm-dialog {
  transform: scale(0.95) translateY(8px);
  opacity: 0;
}

.confirm-modal-leave-to .confirm-dialog {
  transform: scale(0.97) translateY(4px);
  opacity: 0;
}
</style>
