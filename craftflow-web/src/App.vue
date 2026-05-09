<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import { useNetworkStatus } from '@/composables/useNetworkStatus'

useNetworkStatus()
</script>

<template>
  <AppLayout />
  <ToastContainer />
</template>

<style scoped></style>
