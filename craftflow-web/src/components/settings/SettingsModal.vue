<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useTheme } from '@/composables/useTheme'
import { useSettingsStore } from '@/stores/settings'
import type { LlmProfile } from '@/api/types/settings'
import LlmProfileList from './LlmProfileList.vue'
import LlmProfileForm from './LlmProfileForm.vue'
import WritingParams from './WritingParams.vue'

const props = defineProps<{
  visible: boolean
  initialTab?: 'appearance' | 'llm' | 'writing'
}>()

const emit = defineEmits<{
  close: []
}>()

const { theme, setTheme } = useTheme()
const settingsStore = useSettingsStore()

type TabKey = 'appearance' | 'llm' | 'writing'

const tabs: { key: TabKey; label: string; icon: string }[] = [
  { key: 'appearance', label: '外观', icon: 'palette' },
  { key: 'llm', label: 'LLM 配置', icon: 'cpu' },
  { key: 'writing', label: '写作参数', icon: 'pen' },
]

const activeTab = ref<TabKey>(props.initialTab ?? 'appearance')

// Sync activeTab when modal opens with a specific initialTab
watch(
  () => props.visible,
  (val) => {
    if (val && props.initialTab) {
      activeTab.value = props.initialTab
    }
  },
)

// LLM Profile form state
const showForm = ref(false)
const editingProfile = ref<LlmProfile | null>(null)

function handleCreate(): void {
  editingProfile.value = null
  showForm.value = true
}

function handleEdit(profile: LlmProfile): void {
  editingProfile.value = profile
  showForm.value = true
}

function handleCloseForm(): void {
  showForm.value = false
  editingProfile.value = null
}

// Fetch data when switching to relevant tabs
watch(activeTab, (tab) => {
  if (tab === 'llm') {
    settingsStore.fetchProfiles()
  } else if (tab === 'writing') {
    settingsStore.fetchWritingParams()
  }
})

// Escape key to close
function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    if (showForm.value) {
      handleCloseForm()
    } else {
      emit('close')
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})

const themeOptions: { key: 'light' | 'dark'; label: string; desc: string }[] = [
  { key: 'light', label: '浅色', desc: '明亮清爽的界面风格' },
  { key: 'dark', label: '深色', desc: '柔和暗色的界面风格' },
]
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="settings-overlay" @click.self="emit('close')">
        <div class="settings-modal" @click.stop>
          <!-- Header -->
          <div class="modal-header">
            <h2 class="modal-title">设置</h2>
            <button class="btn-close" title="关闭 (Esc)" @click="emit('close')">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <!-- Body: sidebar + content -->
          <div class="modal-body">
            <!-- Left nav -->
            <nav class="settings-nav">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                class="nav-tab"
                :class="{ active: activeTab === tab.key }"
                @click="activeTab = tab.key"
              >
                <!-- Palette icon -->
                <svg v-if="tab.icon === 'palette'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="13.5" cy="6.5" r="2.5" />
                  <circle cx="19" cy="11.5" r="2.5" />
                  <circle cx="6" cy="12" r="2.5" />
                  <circle cx="10" cy="18.5" r="2.5" />
                  <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
                </svg>
                <!-- CPU icon -->
                <svg v-else-if="tab.icon === 'cpu'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
                  <rect x="9" y="9" width="6" height="6" />
                  <line x1="9" y1="1" x2="9" y2="4" />
                  <line x1="15" y1="1" x2="15" y2="4" />
                  <line x1="9" y1="20" x2="9" y2="23" />
                  <line x1="15" y1="20" x2="15" y2="23" />
                  <line x1="20" y1="9" x2="23" y2="9" />
                  <line x1="20" y1="14" x2="23" y2="14" />
                  <line x1="1" y1="9" x2="4" y2="9" />
                  <line x1="1" y1="14" x2="4" y2="14" />
                </svg>
                <!-- Pen icon -->
                <svg v-else-if="tab.icon === 'pen'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 20h9" />
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
                <span>{{ tab.label }}</span>
              </button>
            </nav>

            <!-- Divider -->
            <div class="nav-divider" />

            <!-- Content -->
            <div class="settings-content">
              <!-- Appearance tab -->
              <div v-if="activeTab === 'appearance'" class="tab-panel">
                <h3 class="panel-title">外观设置</h3>
                <p class="panel-desc">选择你喜欢的界面主题风格</p>

                <div class="theme-grid">
                  <button
                    v-for="opt in themeOptions"
                    :key="opt.key"
                    class="theme-card"
                    :class="{ active: theme === opt.key }"
                    @click="setTheme(opt.key)"
                  >
                    <div class="theme-preview" :class="opt.key">
                      <div class="preview-sidebar" />
                      <div class="preview-content">
                        <div class="preview-line w-70" />
                        <div class="preview-line w-50" />
                      </div>
                    </div>
                    <div class="theme-info">
                      <span class="theme-label">{{ opt.label }}</span>
                      <span class="theme-desc">{{ opt.desc }}</span>
                    </div>
                    <div v-if="theme === opt.key" class="theme-check">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                  </button>
                </div>
              </div>

              <!-- LLM tab -->
              <div v-else-if="activeTab === 'llm'" class="tab-panel">
                <h3 class="panel-title">LLM 配置</h3>
                <p class="panel-desc">管理大语言模型的连接配置，支持多个配置切换</p>
                <div class="panel-body">
                  <LlmProfileList @create="handleCreate" @edit="handleEdit" />
                </div>
              </div>

              <!-- Writing tab -->
              <div v-else-if="activeTab === 'writing'" class="tab-panel">
                <h3 class="panel-title">写作参数</h3>
                <p class="panel-desc">调整创作任务的默认参数</p>
                <div class="panel-body">
                  <WritingParams />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- LLM Profile form (nested modal) -->
    <LlmProfileForm
      :visible="showForm"
      :profile="editingProfile"
      @close="handleCloseForm"
      @saved="handleCloseForm"
    />
  </Teleport>
</template>

<style scoped>
/* --- Overlay --- */
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

/* --- Modal shell --- */
.settings-modal {
  width: 860px;
  max-width: 92vw;
  height: 600px;
  max-height: 88vh;
  background: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.2), 0 0 0 1px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  scrollbar-width: none;
}

.settings-modal::-webkit-scrollbar,
.settings-modal *::-webkit-scrollbar {
  display: none;
}

/* --- Header --- */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-lg) var(--space-xl);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.modal-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
}

.btn-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: all var(--transition-fast);
}

.btn-close:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

/* --- Body (sidebar + content) --- */
.modal-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* --- Left nav --- */
.settings-nav {
  width: 180px;
  flex-shrink: 0;
  padding: var(--space-md) var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  text-align: left;
  width: 100%;
  transition: all var(--transition-fast);
}

.nav-tab:hover {
  color: var(--color-text);
  background: var(--color-bg);
}

.nav-tab.active {
  color: var(--color-accent);
  background: var(--color-accent-soft);
  font-weight: 600;
}

.nav-tab svg {
  flex-shrink: 0;
  opacity: 0.65;
}

.nav-tab.active svg {
  opacity: 1;
}

.nav-divider {
  width: 1px;
  background: var(--color-border);
  flex-shrink: 0;
}

/* --- Content area --- */
.settings-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: var(--space-xl) var(--space-xl);
}

.tab-panel {
  animation: fadeSlideIn 200ms ease-out;
}

.panel-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-xs);
}

.panel-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: var(--space-xl);
}

.panel-body {
  /* Reset margins from child components */
}

/* --- Theme cards --- */
.theme-grid {
  display: flex;
  gap: var(--space-md);
}

.theme-card {
  position: relative;
  width: 200px;
  padding: var(--space-md);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  text-align: left;
  transition: all var(--transition-fast);
  cursor: pointer;
}

.theme-card:hover {
  border-color: var(--color-text-muted);
}

.theme-card.active {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.theme-preview {
  width: 100%;
  height: 100px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  display: flex;
  margin-bottom: var(--space-md);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.theme-preview.light {
  background: #FAFAF8;
}

.theme-preview.dark {
  background: #1C1917;
}

.preview-sidebar {
  width: 36%;
  flex-shrink: 0;
}

.theme-preview.light .preview-sidebar {
  background: #1A1A1A;
}

.theme-preview.dark .preview-sidebar {
  background: #0C0A09;
}

.preview-content {
  flex: 1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-line {
  height: 6px;
  border-radius: 3px;
}

.theme-preview.light .preview-line {
  background: #E8E6E1;
}

.theme-preview.dark .preview-line {
  background: #44403C;
}

.preview-line.w-70 { width: 70%; }
.preview-line.w-50 { width: 50%; }

.theme-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.theme-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.theme-desc {
  font-size: 12px;
  color: var(--color-text-muted);
}

.theme-check {
  position: absolute;
  top: var(--space-sm);
  right: var(--space-sm);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* --- Transition --- */
.modal-enter-active {
  transition: opacity 200ms ease;
}

.modal-enter-active .settings-modal {
  transition: transform 250ms cubic-bezier(0.16, 1, 0.3, 1), opacity 200ms ease;
}

.modal-leave-active {
  transition: opacity 150ms ease;
}

.modal-leave-active .settings-modal {
  transition: transform 150ms ease, opacity 150ms ease;
}

.modal-enter-from {
  opacity: 0;
}

.modal-enter-from .settings-modal {
  opacity: 0;
  transform: scale(0.96) translateY(8px);
}

.modal-leave-to {
  opacity: 0;
}

.modal-leave-to .settings-modal {
  opacity: 0;
  transform: scale(0.97) translateY(4px);
}

/* --- Responsive --- */
@media (max-width: 768px) {
  .settings-modal {
    width: 100vw;
    height: 100vh;
    max-width: 100vw;
    max-height: 100vh;
    border-radius: 0;
  }

  .modal-body {
    flex-direction: column;
  }

  .settings-nav {
    width: 100%;
    flex-direction: row;
    padding: var(--space-sm);
    overflow-x: auto;
    overflow-y: hidden;
    border-bottom: 1px solid var(--color-border);
  }

  .nav-divider {
    display: none;
  }

  .nav-tab {
    white-space: nowrap;
    padding: var(--space-sm) var(--space-md);
  }

  .settings-content {
    padding: var(--space-md);
  }

  .theme-grid {
    flex-direction: column;
  }

  .theme-card {
    width: 100%;
  }
}
</style>
