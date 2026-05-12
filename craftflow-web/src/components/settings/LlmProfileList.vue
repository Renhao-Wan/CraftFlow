<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import type { LlmProfile } from '@/api/types/settings'

const store = useSettingsStore()

const emit = defineEmits<{
  edit: [profile: LlmProfile]
  create: []
}>()

onMounted(() => {
  store.fetchProfiles()
})

async function handleDelete(profile: LlmProfile): Promise<void> {
  if (!confirm(`确定删除配置「${profile.name}」吗？`)) return
  await store.removeProfile(profile.id)
}

async function handleSetDefault(profile: LlmProfile): Promise<void> {
  await store.makeDefault(profile.id)
}
</script>

<template>
  <div class="profile-list">
    <div class="profile-list-header">
      <h3 class="section-title">LLM 配置</h3>
      <button class="btn-add" @click="emit('create')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        新增配置
      </button>
    </div>

    <div v-if="store.loading && store.profiles.length === 0" class="loading-hint">
      加载中...
    </div>

    <div v-else-if="store.profiles.length === 0" class="empty-hint">
      暂无 LLM 配置，请点击上方按钮添加
    </div>

    <div v-else class="profile-cards">
      <div
        v-for="profile in store.profiles"
        :key="profile.id"
        class="profile-card"
        :class="{ default: profile.is_default }"
      >
        <div class="profile-card-header">
          <span class="profile-name">{{ profile.name }}</span>
          <span v-if="profile.is_default" class="badge-default">默认</span>
        </div>
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
            @click="handleSetDefault(profile)"
          >
            设为默认
          </button>
          <button class="btn-action btn-edit" @click="emit('edit', profile)">
            编辑
          </button>
          <button class="btn-action btn-delete" @click="handleDelete(profile)">
            删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-list {
  margin-bottom: var(--space-xl);
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

.btn-add:hover {
  background: var(--color-accent-hover);
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
  gap: var(--space-md);
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

.profile-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-md) var(--space-sm);
}

.profile-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--color-text);
}

.badge-default {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  font-weight: 600;
}

.profile-card-body {
  padding: 0 var(--space-md) var(--space-md);
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
</style>
