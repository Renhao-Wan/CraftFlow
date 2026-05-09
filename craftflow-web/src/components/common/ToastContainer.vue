<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, remove } = useToast()

function typeClass(type: string): string {
  return 'toast-' + type
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-container" aria-live="polite">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-item"
          :class="typeClass(toast.type)"
          @click="remove(toast.id)"
        >
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-close" aria-label="关闭">&times;</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: var(--space-lg);
  left: calc(var(--sidebar-width) + var(--space-lg));
  right: var(--space-lg);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  max-width: 400px;
  pointer-events: none;
}

@media (max-width: 768px) {
  .toast-container {
    top: calc(var(--header-height) + var(--space-sm));
    left: var(--space-md);
    right: var(--space-md);
  }
}

.toast-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  pointer-events: auto;
}

.toast-info {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
}

.toast-success {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.toast-warning {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.toast-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.toast-message {
  flex: 1;
  font-size: 14px;
  line-height: 1.4;
}

.toast-close {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0.5;
  transition: opacity 0.15s;
  color: inherit;
  padding: 0;
}

.toast-close:hover {
  opacity: 1;
}

.toast-enter-active {
  transition: all 0.25s ease-out;
}

.toast-leave-active {
  transition: all 0.2s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>
