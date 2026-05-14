/** 设置 API — REST 通道 */

import client from '@/api/client'
import type { TestProfileResponse } from '@/api/types/chat'
import type {
  LlmProfile,
  LlmProfileRequest,
  ToolConfigs,
  ToolConfigsRequest,
  WritingParams,
  WritingParamsRequest,
} from '@/api/types/settings'

/** 获取所有 LLM Profile */
export async function getLlmProfiles(): Promise<LlmProfile[]> {
  return client.get('/v1/settings/llm-profiles')
}

/** 创建 LLM Profile */
export async function createLlmProfile(
  data: LlmProfileRequest,
): Promise<LlmProfile> {
  return client.post('/v1/settings/llm-profiles', data)
}

/** 更新 LLM Profile */
export async function updateLlmProfile(
  profileId: string,
  data: LlmProfileRequest,
): Promise<LlmProfile> {
  return client.put(`/v1/settings/llm-profiles/${profileId}`, data)
}

/** 删除 LLM Profile */
export async function deleteLlmProfile(
  profileId: string,
): Promise<void> {
  await client.delete(`/v1/settings/llm-profiles/${profileId}`)
}

/** 设为默认 Profile */
export async function setDefaultProfile(
  profileId: string,
): Promise<void> {
  await client.post(`/v1/settings/llm-profiles/${profileId}/set-default`)
}

/** 获取写作参数 */
export async function getWritingParams(): Promise<WritingParams> {
  return client.get('/v1/settings/writing-params')
}

/** 更新写作参数 */
export async function updateWritingParams(
  data: WritingParamsRequest,
): Promise<WritingParams> {
  return client.patch('/v1/settings/writing-params', data)
}

/** 获取外部工具配置（脱敏） */
export async function getToolConfigs(): Promise<ToolConfigs> {
  return client.get('/v1/settings/tool-configs')
}

/** 更新外部工具配置 */
export async function updateToolConfigs(
  data: ToolConfigsRequest,
): Promise<ToolConfigs> {
  return client.patch('/v1/settings/tool-configs', data)
}

/** 测试 LLM Profile 连接 */
export async function testLlmProfile(
  profileId: string,
): Promise<TestProfileResponse> {
  return client.post(`/v1/settings/llm-profiles/${profileId}/test`)
}
