<script setup lang="ts">
import { ref } from 'vue'
import LlmProfileList from '@/components/settings/LlmProfileList.vue'
import LlmProfileForm from '@/components/settings/LlmProfileForm.vue'
import WritingParams from '@/components/settings/WritingParams.vue'
import type { LlmProfile } from '@/api/types/settings'

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

function handleClose(): void {
  showForm.value = false
  editingProfile.value = null
}
</script>

<template>
  <div class="settings-page">
    <div class="settings-header">
      <h1 class="page-title">设置</h1>
      <p class="page-desc">管理 LLM 配置和写作参数</p>
    </div>

    <div class="settings-body">
      <LlmProfileList @create="handleCreate" @edit="handleEdit" />
      <WritingParams />
    </div>

    <LlmProfileForm
      :visible="showForm"
      :profile="editingProfile"
      @close="handleClose"
      @saved="handleClose"
    />
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-2xl) var(--space-lg);
  animation: fadeSlideIn 400ms ease-out;
}

.settings-header {
  margin-bottom: var(--space-2xl);
}

.page-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--space-sm);
}

.page-desc {
  font-size: 14px;
  color: var(--color-text-muted);
}

.settings-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xl);
}
</style>
