<script setup lang="ts">
import type { TaskStatus } from '@/api/types/task'

const props = defineProps<{
  status: TaskStatus
}>()

const statusConfig: Record<TaskStatus, { label: string; className: string }> = {
  running: { label: '运行中', className: 'badge-running' },
  interrupted: { label: '已中断', className: 'badge-interrupted' },
  completed: { label: '已完成', className: 'badge-completed' },
  failed: { label: '失败', className: 'badge-failed' },
}
</script>

<template>
  <span class="badge" :class="statusConfig[props.status].className">
    {{ statusConfig[props.status].label }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
}

.badge-running {
  background: #dbeafe;
  color: #1d4ed8;
}

.badge-interrupted {
  background: #fef3c7;
  color: #b45309;
}

.badge-completed {
  background: #dcfce7;
  color: #15803d;
}

.badge-failed {
  background: #fee2e2;
  color: #b91c1c;
}
</style>
