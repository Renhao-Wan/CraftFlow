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
  background: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.error-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #b91c1c;
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
  color: #991b1b;
  line-height: 1.5;
}

.retry-btn {
  margin-top: 8px;
  padding: 4px 16px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  transition: background 0.2s;
}

.retry-btn:hover {
  background: #f3f4f6;
}
</style>
