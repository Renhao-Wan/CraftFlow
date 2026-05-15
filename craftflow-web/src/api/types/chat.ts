/** 对话消息 — 单条消息 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** SSE 流式对话请求 — POST /api/v1/chat */
export interface ChatRequest {
  messages: ChatMessage[]
  profile_id?: string
}

/** SSE 流式响应 chunk */
export interface ChatChunk {
  content: string
  done: boolean
  error?: string
}

/** LLM Profile 连接测试响应 — POST /api/v1/settings/llm-profiles/{id}/test */
export interface TestProfileResponse {
  success: boolean
  reply?: string
  error?: string
  latency_ms?: number
}
