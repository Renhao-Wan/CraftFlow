<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    percentage: number
    showText?: boolean
    height?: number
  }>(),
  {
    showText: true,
    height: 8,
  },
)

const clampedPercentage = computed(() => Math.min(100, Math.max(0, props.percentage)))
</script>

<script lang="ts">
import { computed } from 'vue'
</script>

<template>
  <div class="progress-wrapper">
    <div class="progress-track" :style="{ height: `${height}px` }">
      <div
        class="progress-fill"
        :style="{ width: `${clampedPercentage}%` }"
      />
    </div>
    <span v-if="showText" class="progress-text">{{ Math.round(clampedPercentage) }}%</span>
  </div>
</template>

<style scoped>
.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.progress-track {
  flex: 1;
  background: #e5e7eb;
  border-radius: 9999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #2563eb;
  border-radius: 9999px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  min-width: 40px;
  text-align: right;
}
</style>
