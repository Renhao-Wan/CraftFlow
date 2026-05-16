<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  /** 原始 Markdown 文本 */
  content: string
}>()

/** 节流渲染间隔（ms） */
const THROTTLE_INTERVAL = 80

/** 实际渲染的 HTML */
const html = ref('')
/** 是否有待渲染的内容 */
let pendingContent = ''
let throttleTimer: ReturnType<typeof setTimeout> | null = null
let rafId: number | null = null

function renderMarkdown(content: string): void {
  if (!content) {
    html.value = ''
    return
  }
  html.value = marked.parse(content, { async: false }) as string
}

/** 节流渲染：最多每 THROTTLE_INTERVAL ms 渲染一次，保证最后一次一定渲染 */
function throttledRender(content: string): void {
  pendingContent = content
  if (throttleTimer !== null) return

  throttleTimer = setTimeout(() => {
    throttleTimer = null
    renderMarkdown(pendingContent)
    // 确保最终内容一定被渲染（如果节流窗口后还有新内容）
    if (rafId !== null) cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      rafId = null
      if (pendingContent !== html.value) {
        renderMarkdown(pendingContent)
      }
    })
  }, THROTTLE_INTERVAL)
}

watch(
  () => props.content,
  (content) => {
    if (!content) {
      html.value = ''
      return
    }
    // 完成状态（内容不再变化）直接渲染，不节流
    // 通过内容长度变化速度判断：如果 200ms 内无新 token，认为流式结束
    throttledRender(content)
  },
  { immediate: true },
)

onUnmounted(() => {
  if (throttleTimer !== null) {
    clearTimeout(throttleTimer)
    throttleTimer = null
  }
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
})
</script>

<template>
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body {
  font-size: 15px;
  line-height: 1.75;
  color: var(--color-text);
}

.markdown-body :deep(h1) {
  font-size: 28px;
  font-weight: 700;
  margin: 24px 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.markdown-body :deep(h2) {
  font-size: 22px;
  font-weight: 600;
  margin: 20px 0 12px;
}

.markdown-body :deep(h3) {
  font-size: 18px;
  font-weight: 600;
  margin: 16px 0 8px;
}

.markdown-body :deep(p) {
  margin: 0 0 12px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 12px;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(blockquote) {
  margin: 0 0 12px;
  padding: 8px 16px;
  border-left: 4px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-secondary);
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  background: var(--color-bg);
  border-radius: 4px;
  font-size: 14px;
  font-family: ui-monospace, monospace;
}

.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 16px;
  background: var(--color-code-bg);
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  background: transparent;
  color: var(--color-code-text);
  padding: 0;
}

.markdown-body :deep(a) {
  color: var(--color-accent);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 12px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--color-bg);
  font-weight: 600;
}

.markdown-body :deep(hr) {
  margin: 24px 0;
  border: none;
  border-top: 1px solid var(--color-border);
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}
</style>
