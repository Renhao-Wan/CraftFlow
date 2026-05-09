/** 创作任务请求 — POST /api/v1/creation */
export interface CreationRequest {
  /** 文章主题，1-500 字符 */
  topic: string
  /** 补充描述或需求说明，0-2000 字符 */
  description?: string
}
