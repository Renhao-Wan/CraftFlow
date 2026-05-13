<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from './AppSidebar.vue'
import SettingsModal from '@/components/settings/SettingsModal.vue'

const settingsVisible = ref(false)

function openSettings(): void {
  settingsVisible.value = true
}

function closeSettings(): void {
  settingsVisible.value = false
}
</script>

<template>
  <div class="app-layout">
    <AppSidebar @open-settings="openSettings" />
    <main class="app-content">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>

  <SettingsModal :visible="settingsVisible" @close="closeSettings" />
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
}

.app-content {
  flex: 1;
  margin-left: var(--sidebar-width);
  min-height: 100vh;
  background: var(--color-bg);
  padding: var(--space-xl) var(--space-2xl);
}

/* Page transition */
.page-fade-enter-active {
  animation: fadeSlideIn 300ms ease-out;
}

.page-fade-leave-active {
  animation: fadeIn 150ms ease reverse;
}

/* Mobile: no sidebar offset, add top padding for mobile header */
@media (max-width: 768px) {
  .app-content {
    margin-left: 0;
    padding: calc(var(--header-height) + var(--space-md)) var(--space-md) var(--space-md);
  }
}
</style>
