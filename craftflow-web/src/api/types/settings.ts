/** LLM Profile — GET /api/v1/settings/llm-profiles */
export interface LlmProfile {
  id: string
  name: string
  api_key: string
  api_base: string
  model: string
  temperature: number
  is_default: boolean
  created_at: string
  updated_at: string
}

/** LLM Profile 创建/更新请求 */
export interface LlmProfileRequest {
  name: string
  api_key: string
  api_base?: string
  model: string
  temperature?: number
  is_default?: boolean
}

/** 写作参数 — GET /api/v1/settings/writing-params */
export interface WritingParams {
  max_outline_sections: number
  max_concurrent_writers: number
}

/** 写作参数更新请求 */
export interface WritingParamsRequest {
  max_outline_sections?: number
  max_concurrent_writers?: number
}
