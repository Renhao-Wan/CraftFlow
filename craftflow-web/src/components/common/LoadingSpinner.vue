<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number
    label?: string
  }>(),
  {
    size: 24,
    label: '加载中...',
  },
)
</script>

<template>
  <div class="spinner-container">
    <svg
      class="spinner"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="#e5e7eb"
        stroke-width="3"
      />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="#2563eb"
        stroke-width="3"
        stroke-linecap="round"
      />
    </svg>
    <span v-if="label" class="spinner-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.spinner-container {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  animation: spin 0.8s linear infinite;
}

.spinner-label {
  font-size: 14px;
  color: #6b7280;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
