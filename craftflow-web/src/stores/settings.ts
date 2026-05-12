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
  const writingParams = ref<WritingParams>({
    max_outline_sections: 5,
    max_concurrent_writers: 3,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ─── Actions ────────────────────────────────────────────

  /** 加载所有 LLM Profile */
  async function fetchProfiles(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      profiles.value = await getLlmProfiles()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载 LLM 配置失败'
      throw e
    } finally {
      loading.value = false
    }
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
    writingParams,
    loading,
    error,
    fetchProfiles,
    addProfile,
    editProfile,
    removeProfile,
    makeDefault,
    fetchWritingParams,
    saveWritingParams,
  }
})
