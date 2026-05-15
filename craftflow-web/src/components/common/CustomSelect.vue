<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

export interface SelectOption {
  value: string
  label: string
  sublabel?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    options: SelectOption[]
    placeholder?: string
  }>(),
  {
    placeholder: '请选择',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isOpen = ref(false)
const containerRef = ref<HTMLElement | null>(null)

const selectedOption = computed(() =>
  props.options.find((opt) => opt.value === props.modelValue),
)

function toggle(): void {
  isOpen.value = !isOpen.value
}

function select(value: string): void {
  emit('update:modelValue', value)
  isOpen.value = false
}

function handleClickOutside(e: MouseEvent): void {
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div ref="containerRef" class="custom-select" :class="{ open: isOpen }">
    <!-- 选中态 -->
    <button class="select-trigger" @click="toggle">
      <span class="trigger-text">
        <span v-if="selectedOption" class="trigger-label">{{ selectedOption.label }}</span>
        <span v-else class="trigger-placeholder">{{ placeholder }}</span>
      </span>
      <svg
        class="trigger-chevron"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>

    <!-- 下拉列表 -->
    <Transition name="dropdown">
      <div v-if="isOpen" class="select-dropdown">
        <button
          v-for="opt in options"
          :key="opt.value"
          class="dropdown-item"
          :class="{ active: opt.value === modelValue }"
          @click="select(opt.value)"
        >
          <span class="item-label">{{ opt.label }}</span>
          <span v-if="opt.sublabel" class="item-sublabel">{{ opt.sublabel }}</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.custom-select {
  position: relative;
  width: 240px;
}

/* ── 选中态 ── */

.select-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
  cursor: pointer;
  transition: border-color var(--transition-fast);
  text-align: left;
}

.select-trigger:hover {
  border-color: var(--color-accent);
}

.custom-select.open .select-trigger {
  border-color: var(--color-accent);
}

.trigger-text {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 13px;
}

.trigger-label {
  color: var(--color-text);
  font-weight: 500;
}

.trigger-placeholder {
  color: var(--color-text-muted);
}

.trigger-chevron {
  flex-shrink: 0;
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.custom-select.open .trigger-chevron {
  transform: rotate(180deg);
}

/* ── 下拉列表 ── */

.select-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  width: 100%;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 100;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}

.dropdown-item {
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
  width: 100%;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
  text-align: left;
}

.dropdown-item:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.04));
}

.dropdown-item.active {
  background: var(--color-accent-soft);
}

.item-label {
  flex-shrink: 0;
  max-width: 50%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.item-sublabel {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--color-text-muted);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* ── 动画 ── */

.dropdown-enter-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.dropdown-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── 滚动条 ── */

.select-dropdown::-webkit-scrollbar {
  width: 4px;
}

.select-dropdown::-webkit-scrollbar-track {
  background: transparent;
}

.select-dropdown::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

.select-dropdown::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-muted);
}
</style>
