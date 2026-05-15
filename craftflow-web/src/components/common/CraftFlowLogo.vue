<script setup lang="ts">
defineProps<{
  size?: number
}>()
</script>

<template>
  <svg
    :width="size || 32"
    :height="size || 32"
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <rect width="32" height="32" rx="8" fill="var(--color-accent)" />
    <path d="M8 16L14 10L20 16L14 22L8 16Z" fill="white" />
    <path d="M14 16L20 10L26 16L20 22L14 16Z" fill="white" opacity="0.6" />
  </svg>
</template>
