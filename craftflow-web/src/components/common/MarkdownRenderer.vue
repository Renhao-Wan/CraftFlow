<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  /** 原始 Markdown 文本 */
  content: string
}>()

/** 将 Markdown 转换为 HTML */
const html = computed(() => {
  if (!props.content) return ''
  return marked.parse(props.content, { async: false }) as string
})
</script>

<template>
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body {
  font-size: 15px;
  line-height: 1.75;
  color: #1f2937;
}

.markdown-body :deep(h1) {
  font-size: 28px;
  font-weight: 700;
  margin: 24px 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
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
  border-left: 4px solid #d1d5db;
  background: #f9fafb;
  color: #6b7280;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  background: #f3f4f6;
  border-radius: 4px;
  font-size: 14px;
  font-family: ui-monospace, monospace;
}

.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 16px;
  background: #1f2937;
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  background: transparent;
  color: #e5e7eb;
  padding: 0;
}

.markdown-body :deep(a) {
  color: #2563eb;
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
  border: 1px solid #e5e7eb;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f9fafb;
  font-weight: 600;
}

.markdown-body :deep(hr) {
  margin: 24px 0;
  border: none;
  border-top: 1px solid #e5e7eb;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}
</style>
