<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import AppSidebar from './AppSidebar.vue'
import SettingsModal from '@/components/settings/SettingsModal.vue'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const sidebarCollapsed = ref(false)

onMounted(() => {
  const saved = localStorage.getItem('sidebar-collapsed')
  if (saved === 'true') {
    sidebarCollapsed.value = true
  }
})

watch(sidebarCollapsed, (val) => {
  localStorage.setItem('sidebar-collapsed', String(val))
})

function toggleSidebarCollapse(): void {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function openSettings(): void {
  settingsStore.openSettingsModal()
}
</script>

<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <AppSidebar
      :collapsed="sidebarCollapsed"
      @open-settings="openSettings"
      @toggle-collapse="toggleSidebarCollapse"
    />
    <main class="app-content">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>

  <SettingsModal
    :visible="settingsStore.settingsModalVisible"
    :initial-tab="settingsStore.settingsInitialTab"
    @close="settingsStore.closeSettingsModal()"
  />
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
}

.app-content {
  flex: 1;
  margin-left: var(--sidebar-width);
  height: 100vh;
  overflow-y: auto;
  background: var(--color-bg);
  padding: var(--space-xl) var(--space-2xl);
  transition: margin-left var(--transition-normal);
}

/* Page transition */
.page-fade-enter-active {
  animation: fadeSlideIn 300ms ease-out;
}

.page-fade-leave-active {
  animation: fadeIn 150ms ease reverse;
}

/* Collapsed sidebar state */
.sidebar-collapsed .app-content {
  margin-left: var(--sidebar-collapsed-width);
}

/* Mobile: no sidebar offset, add top padding for mobile header */
@media (max-width: 768px) {
  .app-content {
    margin-left: 0;
    padding: calc(var(--header-height) + var(--space-md)) var(--space-md) var(--space-md);
  }
}
</style>

<style>
/* Enlarge page max-width to match reduced sidebar width (220px vs original 240px) */
.home-page { max-width: 760px; }
.chat-page { max-width: 960px; }
.history-page { max-width: 880px; }
.task-create-page,
.polishing-create-page { max-width: 800px; }
.task-detail-page { max-width: 960px; }
.polishing-result-page { max-width: 1120px; }
</style>
