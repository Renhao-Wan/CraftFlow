/** 润色模式 */
export type PolishingMode = 1 | 2 | 3

/** 润色模式元信息 */
export const POLISHING_MODE_META: Record<
  PolishingMode,
  { label: string; description: string; extra?: string }
> = {
  1: {
    label: '快速排版',
    description: '自动修正格式、统一标题层级、优化排版，让文章整洁易读，不改变原文内容',
    extra: '约 15 秒 ， 文本长度越长时间越久',
  },
  2: {
    label: '深度润色',
    description: '优化语言表达、加强逻辑衔接、补充细节，全面提升文章质量',
    extra: '约 40 秒 · 推荐 ， 文本长度越长时间越久',
  },
  3: {
    label: '事实核查',
    description: '核查文章中的数据、引用、时间等事实性内容，标注问题并给出修正建议，若存在问题则会进行深度润色',
    extra: '约 10 ~ 50 秒 ， 取决于文章中事实性内容的多少和复杂程度，文本长度越长时间越久',
  },
}

/** 润色任务请求 — POST /api/v1/polishing */
export interface PolishingRequest {
  /** 待润色的文章内容（Markdown 格式），>=10 字符 */
  content: string
  /** 润色模式：1=快速排版, 2=深度润色, 3=事实核查 */
  mode: PolishingMode
}
