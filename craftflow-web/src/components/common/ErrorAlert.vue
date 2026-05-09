<script setup lang="ts">
defineProps<{
  message: string
  retryable?: boolean
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="error-alert">
    <div class="error-icon">!</div>
    <div class="error-content">
      <p class="error-message">{{ message }}</p>
      <button v-if="retryable" class="retry-btn" @click="$emit('retry')">
        重试
      </button>
    </div>
  </div>
</template>

<style scoped>
.error-alert {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: var(--color-error-bg);
  border: 1px solid var(--color-error);
  border-radius: 8px;
}

.error-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-error);
  color: #fff;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 700;
}

.error-content {
  flex: 1;
}

.error-message {
  margin: 0;
  font-size: 14px;
  color: var(--color-error);
  line-height: 1.5;
}

.retry-btn {
  margin-top: 8px;
  padding: 4px 16px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
  color: var(--color-text);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.retry-btn:hover {
  background: var(--color-bg);
}
</style>
