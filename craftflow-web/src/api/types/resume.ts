/** 恢复动作类型 */
export type ResumeAction =
  | 'confirm_outline'
  | 'update_outline'
  | 'approve_draft'
  | 'reject_draft'

/** 任务恢复请求 — POST /api/v1/tasks/{task_id}/resume */
export interface ResumeRequest {
  action: ResumeAction
  /** 注入的数据（如修改后的大纲） */
  data?: Record<string, unknown>
}
