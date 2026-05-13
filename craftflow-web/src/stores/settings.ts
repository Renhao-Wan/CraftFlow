import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getLlmProfiles,
  createLlmProfile,
  updateLlmProfile,
  deleteLlmProfile,
  setDefaultProfile,
  getWritingParams,
  updateWritingParams,
} from '@/api/settings'
import type {
  LlmProfile,
  LlmProfileRequest,
  WritingParams,
  WritingParamsRequest,
} from '@/api/types/settings'

export const useSettingsStore = defineStore('settings', () => {
  // ─── State ──────────────────────────────────────────────
  const profiles = ref<LlmProfile[]>([])
  const profilesLoaded = ref(false)
  const writingParams = ref<WritingParams>({
    max_outline_sections: 5,
    max_concurrent_writers: 3,
    max_debate_iterations: 3,
    editor_pass_score: 90,
    task_timeout: 3600,
    tool_call_timeout: 30,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ─── Settings Modal State ───────────────────────────────
  const settingsModalVisible = ref(false)
  const settingsInitialTab = ref<'appearance' | 'llm' | 'writing'>('appearance')

  function openSettingsModal(tab: 'appearance' | 'llm' | 'writing' = 'appearance'): void {
    settingsInitialTab.value = tab
    settingsModalVisible.value = true
  }

  function closeSettingsModal(): void {
    settingsModalVisible.value = false
  }

  // ─── Actions ────────────────────────────────────────────

  /** 加载所有 LLM Profile */
  async function fetchProfiles(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      profiles.value = await getLlmProfiles()
      profilesLoaded.value = true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载 LLM 配置失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 检查是否有 LLM Profile（首次调用会 fetch，之后用缓存） */
  async function checkProfiles(): Promise<boolean> {
    if (!profilesLoaded.value) {
      await fetchProfiles()
    }
    return profiles.value.length > 0
  }

  /** 创建 LLM Profile */
  async function addProfile(data: LlmProfileRequest): Promise<LlmProfile> {
    loading.value = true
    error.value = null
    try {
      const profile = await createLlmProfile(data)
      await fetchProfiles()
      return profile
    } catch (e) {
      error.value = e instanceof Error ? e.message : '创建 LLM 配置失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 更新 LLM Profile */
  async function editProfile(
    profileId: string,
    data: LlmProfileRequest,
  ): Promise<LlmProfile> {
    loading.value = true
    error.value = null
    try {
      const profile = await updateLlmProfile(profileId, data)
      await fetchProfiles()
      return profile
    } catch (e) {
      error.value = e instanceof Error ? e.message : '更新 LLM 配置失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 删除 LLM Profile */
  async function removeProfile(profileId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await deleteLlmProfile(profileId)
      await fetchProfiles()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '删除 LLM 配置失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 设为默认 Profile */
  async function makeDefault(profileId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await setDefaultProfile(profileId)
      await fetchProfiles()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '切换默认配置失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 加载写作参数 */
  async function fetchWritingParams(): Promise<void> {
    try {
      writingParams.value = await getWritingParams()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载写作参数失败'
    }
  }

  /** 更新写作参数 */
  async function saveWritingParams(data: WritingParamsRequest): Promise<void> {
    try {
      writingParams.value = await updateWritingParams(data)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '更新写作参数失败'
      throw e
    }
  }

  return {
    profiles,
    profilesLoaded,
    writingParams,
    loading,
    error,
    settingsModalVisible,
    settingsInitialTab,
    openSettingsModal,
    closeSettingsModal,
    checkProfiles,
    fetchProfiles,
    addProfile,
    editProfile,
    removeProfile,
    makeDefault,
    fetchWritingParams,
    saveWritingParams,
  }
})
