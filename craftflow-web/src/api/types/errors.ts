/** 后端错误响应结构 */
export interface ErrorResponse {
  error: string
  message: string
  detail?: Record<string, unknown>
  timestamp: string
  path?: string
}

/** 前端 API 调用异常 */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly data?: ErrorResponse,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
