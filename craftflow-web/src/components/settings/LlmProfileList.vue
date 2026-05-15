<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { testLlmProfile } from '@/api/settings'
import ConfirmDeleteModal from '@/components/common/ConfirmDeleteModal.vue'
import type { LlmProfile } from '@/api/types/settings'
import type { TestProfileResponse } from '@/api/types/chat'

const store = useSettingsStore()
const router = useRouter()

const emit = defineEmits<{
  edit: [profile: LlmProfile]
  create: []
}>()

const MAX_PROFILES = 20

// ─── 测试连接状态 ────────────────────────────────────────
const testingProfileId = ref<string | null>(null)
const testResult = ref<TestProfileResponse | null>(null)
const testLoading = ref(false)
const ACCORDION_STORAGE_KEY = 'craftflow:llm-profile-accordion'

const searchQuery = ref('')
const expandedIds = ref<Set<string>>(new Set())
const accordionMode = ref(loadAccordionMode())
const showTooltip = ref(false)

// 删除确认弹窗状态
const deleteModalVisible = ref(false)
const deleteModalLoading = ref(false)
const deleteTargetProfile = ref<LlmProfile | null>(null)

function loadAccordionMode(): boolean {
  const stored = localStorage.getItem(ACCORDION_STORAGE_KEY)
  return stored === null ? true : stored === 'true'
}

function toggleAccordionMode(): void {
  accordionMode.value = !accordionMode.value
  localStorage.setItem(ACCORDION_STORAGE_KEY, String(accordionMode.value))
  if (accordionMode.value && expandedIds.value.size > 1) {
    const first = expandedIds.value.values().next().value
    expandedIds.value = new Set(first ? [first] : [])
  }
}

const canCreate = computed(() => store.profiles.length < MAX_PROFILES)

const filteredProfiles = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return store.profiles
  return store.profiles.filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      p.model.toLowerCase().includes(q),
  )
})

function toggleExpand(id: string): void {
  if (expandedIds.value.has(id)) {
    expandedIds.value = new Set([...expandedIds.value].filter((i) => i !== id))
  } else {
    expandedIds.value = accordionMode.value
      ? new Set([id])
      : new Set([...expandedIds.value, id])
  }
}

onMounted(() => {
  store.fetchProfiles()
})

function promptDelete(profile: LlmProfile): void {
  deleteTargetProfile.value = profile
  deleteModalVisible.value = true
}

async function confirmDelete(): Promise<void> {
  if (!deleteTargetProfile.value) return
  deleteModalLoading.value = true
  try {
    await store.removeProfile(deleteTargetProfile.value.id)
    deleteModalVisible.value = false
  } catch {
    // store 已设置 error
  } finally {
    deleteModalLoading.value = false
  }
}

async function handleSetDefault(profile: LlmProfile): Promise<void> {
  await store.makeDefault(profile.id)
}

async function handleTest(profile: LlmProfile): Promise<void> {
  testingProfileId.value = profile.id
  testResult.value = null
  testLoading.value = true
  try {
    testResult.value = await testLlmProfile(profile.id)
  } catch {
    testResult.value = { success: false, error: '请求失败，请检查网络连接' }
  } finally {
    testLoading.value = false
  }
}

function closeTest(): void {
  testingProfileId.value = null
  testResult.value = null
}

function goToChat(profileId: string): void {
  store.closeSettingsModal()
  router.push({ path: '/chat', query: { profile_id: profileId } })
}
</script>

<template>
  <div class="profile-list">
    <div class="profile-list-sticky">
      <div class="profile-list-header">
        <h3 class="section-title">LLM 配置 <span class="profile-count">{{ store.profiles.length }}/{{ MAX_PROFILES }}</span></h3>
        <div class="header-actions">
          <div
            class="tooltip-wrapper"
            @mouseenter="showTooltip = true"
            @mouseleave="showTooltip = false"
          >
            <button
              class="btn-accordion-toggle"
              @click="toggleAccordionMode"
            >
              <svg v-if="accordionMode" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="3" y1="12" x2="21" y2="12" />
              </svg>
              <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="3" y1="9" x2="21" y2="9" />
                <line x1="3" y1="15" x2="21" y2="15" />
              </svg>
            </button>
            <Transition name="tooltip">
              <div v-if="showTooltip" class="tooltip-bubble">
                {{ accordionMode ? '手风琴模式' : '独立展开模式' }}
                <span class="tooltip-hint">点击切换</span>
              </div>
            </Transition>
          </div>
          <button class="btn-add" :disabled="!canCreate" :title="!canCreate ? `最多 ${MAX_PROFILES} 个配置` : ''" @click="emit('create')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          新增配置
        </button>
        </div>
      </div>
      <div v-if="store.profiles.length > 0" class="search-bar">
        <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索配置名称或模型..."
        />
      </div>
    </div>

    <div v-if="store.loading && store.profiles.length === 0" class="loading-hint">
      加载中...
    </div>

    <div v-else-if="store.profiles.length === 0" class="empty-hint">
      暂无 LLM 配置，请点击上方按钮添加
    </div>

    <div v-else-if="filteredProfiles.length === 0" class="empty-hint">
      未找到匹配的配置
    </div>

    <div v-else class="profile-cards">
      <div
        v-for="profile in filteredProfiles"
        :key="profile.id"
        class="profile-card"
        :class="{ default: profile.is_default, expanded: expandedIds.has(profile.id) }"
      >
        <div class="profile-card-summary" @click="toggleExpand(profile.id)">
          <svg class="expand-icon" :class="{ open: expandedIds.has(profile.id) }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
          <span class="profile-name">{{ profile.name }}</span>
          <span v-if="profile.is_default" class="badge-default">默认</span>
          <span class="profile-model-short">{{ profile.model }}</span>
        </div>
        <div v-if="expandedIds.has(profile.id)" class="profile-card-detail">
          <div class="profile-card-body">
            <div class="profile-field">
              <span class="field-label">模型</span>
              <span class="field-value">{{ profile.model }}</span>
            </div>
            <div class="profile-field">
              <span class="field-label">温度</span>
              <span class="field-value">{{ profile.temperature }}</span>
            </div>
            <div class="profile-field">
              <span class="field-label">API Base</span>
              <span class="field-value">{{ profile.api_base || '默认' }}</span>
            </div>
          </div>
          <div class="profile-card-actions">
            <button
              v-if="!profile.is_default"
              class="btn-action btn-default"
              @click.stop="handleSetDefault(profile)"
            >
              设为默认
            </button>
            <button class="btn-action btn-edit" @click.stop="emit('edit', profile)">
              编辑
            </button>
            <button class="btn-action btn-test" @click.stop="handleTest(profile)">
              测试连接
            </button>
            <button class="btn-action btn-chat" @click.stop="goToChat(profile.id)">
              对话
            </button>
            <button class="btn-action btn-delete" @click.stop="promptDelete(profile)">
              删除
            </button>
          </div>
          <!-- 测试结果内嵌区域 -->
          <div v-if="testingProfileId === profile.id" class="test-result-area">
            <div v-if="testLoading" class="test-loading">
              <span class="test-spinner" />
              正在测试连接...
            </div>
            <div v-else-if="testResult" class="test-result" :class="testResult.success ? 'test-success' : 'test-fail'">
              <div class="test-result-header">
                <svg v-if="testResult.success" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
                <span v-if="testResult.success">
                  连接成功
                  <span v-if="testResult.latency_ms" class="test-latency">（{{ testResult.latency_ms }}ms）</span>
                </span>
                <span v-else>连接失败</span>
              </div>
              <p v-if="testResult.reply" class="test-reply">{{ testResult.reply }}</p>
              <p v-if="testResult.error" class="test-error-msg">{{ testResult.error }}</p>
              <div class="test-result-actions">
                <button class="btn-test-action" @click.stop="handleTest(profile)">重新测试</button>
                <button class="btn-test-action" @click.stop="closeTest">关闭</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <ConfirmDeleteModal
      v-model:visible="deleteModalVisible"
      title="删除配置"
      :message="deleteTargetProfile ? `确定删除 LLM 配置「${deleteTargetProfile.name}」吗？此操作不可恢复。` : ''"
      confirm-text="删除"
      :loading="deleteModalLoading"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.profile-list {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.profile-list-sticky {
  margin-bottom: var(--space-md);
}

.profile-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}

.section-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
}

.profile-count {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 400;
  color: var(--color-text-muted);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.tooltip-wrapper {
  position: relative;
  display: flex;
}

.btn-accordion-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-accordion-toggle:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.tooltip-bubble {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-tooltip-text);
  background: var(--color-tooltip-bg);
  border-radius: var(--radius-md);
  white-space: nowrap;
  box-shadow: var(--shadow-lg);
  pointer-events: none;
  z-index: 50;
}

.tooltip-bubble::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: var(--color-tooltip-bg);
}

.tooltip-hint {
  font-size: 11px;
  font-weight: 400;
  color: var(--color-tooltip-text-muted);
}

.tooltip-enter-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.tooltip-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}

.tooltip-enter-from,
.tooltip-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(4px);
}

.btn-add {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  transition: background var(--transition-fast);
}

.btn-add:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.btn-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.search-bar {
  position: relative;
}

.search-icon {
  position: absolute;
  left: var(--space-md);
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: var(--space-sm) var(--space-md) var(--space-sm) calc(var(--space-md) + 22px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
  color: var(--color-text);
  font-size: 13px;
  transition: border-color var(--transition-fast);
}

.search-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

.loading-hint,
.empty-hint {
  padding: var(--space-xl);
  text-align: center;
  color: var(--color-text-muted);
  font-size: 14px;
}

.profile-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.profile-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
  overflow: hidden;
  transition: box-shadow var(--transition-fast);
}

.profile-card:hover {
  box-shadow: var(--shadow-md);
}

.profile-card.default {
  border-color: var(--color-accent);
}

/* ── 折叠态摘要行 ── */

.profile-card-summary {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  cursor: pointer;
  user-select: none;
  transition: background var(--transition-fast);
}

.profile-card-summary:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.02));
}

.expand-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.expand-icon.open {
  transform: rotate(90deg);
}

.profile-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-text);
}

.profile-model-short {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--color-text-muted);
  margin-left: auto;
}

.badge-default {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  font-weight: 600;
  flex-shrink: 0;
}

/* ── 展开态详情 ── */

.profile-card-detail {
  animation: slideDown 150ms ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.profile-card-body {
  padding: 0 var(--space-md) var(--space-md);
  padding-left: calc(var(--space-md) + 14px + var(--space-sm));
  display: flex;
  gap: var(--space-lg);
  flex-wrap: wrap;
}

.profile-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.field-label {
  font-size: 11px;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-value {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}

.profile-card-actions {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md) var(--space-md);
  padding-left: calc(var(--space-md) + 14px + var(--space-sm));
  border-top: 1px solid var(--color-border);
}

.btn-action {
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-default {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}

.btn-default:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.btn-edit {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}

.btn-edit:hover {
  border-color: var(--color-info);
  color: var(--color-info);
}

.btn-delete {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}

.btn-delete:hover {
  border-color: var(--color-error);
  color: var(--color-error);
}

.btn-test {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}

.btn-test:hover {
  border-color: var(--color-success);
  color: var(--color-success);
}

.btn-chat {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}

.btn-chat:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

/* ── 测试结果内嵌区域 ── */

.test-result-area {
  padding: 0 var(--space-md) var(--space-md);
  padding-left: calc(var(--space-md) + 14px + var(--space-sm));
  animation: slideDown 150ms ease;
}

.test-loading {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 13px;
  color: var(--color-text-muted);
  padding: var(--space-sm) 0;
}

.test-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.test-result {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.test-success {
  background: var(--color-success-bg);
  border: 1px solid var(--color-success);
  color: var(--color-success);
}

.test-fail {
  background: var(--color-error-bg);
  border: 1px solid var(--color-error);
  color: var(--color-error);
}

.test-result-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  margin-bottom: var(--space-xs);
}

.test-latency {
  font-weight: 400;
  opacity: 0.8;
}

.test-reply {
  margin: var(--space-xs) 0;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}

.test-error-msg {
  margin: var(--space-xs) 0;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}

.test-result-actions {
  display: flex;
  gap: var(--space-sm);
  margin-top: var(--space-sm);
}

.btn-test-action {
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  transition: all var(--transition-fast);
}

.btn-test-action:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
</style>
