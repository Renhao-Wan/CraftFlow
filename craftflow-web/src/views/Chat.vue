<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useChat } from '@/composables/useChat'
import { useSettingsStore } from '@/stores/settings'
import CustomSelect from '@/components/common/CustomSelect.vue'
import type { SelectOption } from '@/components/common/CustomSelect.vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'

const route = useRoute()
const settingsStore = useSettingsStore()

const { messages, isStreaming, error, send, cancel, clear } = useChat()

const inputText = ref('')
const selectedProfileId = ref<string>('')
const messagesContainer = ref<HTMLElement | null>(null)

const profileOptions = computed<SelectOption[]>(() =>
  settingsStore.profiles.map((p) => ({
    value: p.id,
    label: p.name,
    sublabel: p.model,
  })),
)

// ─── Profile 初始化与同步 ──────────────────────────────────

onMounted(async () => {
  await settingsStore.fetchProfiles()
  syncProfileFromQuery()
})

// 监听 query 参数变化（已在 /chat 页面时从设置页跳转不同模型）
watch(
  () => route.query.profile_id,
  () => syncProfileFromQuery(),
)

function syncProfileFromQuery(): void {
  const queryProfileId = route.query.profile_id as string | undefined
  if (queryProfileId && settingsStore.profiles.some((p) => p.id === queryProfileId)) {
    selectedProfileId.value = queryProfileId
  } else if (!selectedProfileId.value) {
    // 仅在尚未选中时设置默认值，避免覆盖用户手动选择
    const defaultP = settingsStore.profiles.find((p) => p.is_default)
    selectedProfileId.value = defaultP?.id ?? settingsStore.profiles[0]?.id ?? ''
  }
}

// ─── 自动滚动到底部 ────────────────────────────────────────

function scrollToBottom(): void {
  nextTick(() => {
    messagesContainer.value?.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth',
    })
  })
}

watch(
  () => messages.value.length,
  () => scrollToBottom(),
)

watch(
  () => messages.value[messages.value.length - 1]?.content,
  () => scrollToBottom(),
)

// ─── 发送消息 ──────────────────────────────────────────────

async function handleSend(): Promise<void> {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return
  inputText.value = ''
  await send(text, selectedProfileId.value || undefined)
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// ─── 复制对话 ──────────────────────────────────────────────

function copyConversation(): void {
  const text = messages.value
    .map((m) => {
      const label = m.role === 'user' ? '**用户**' : '**AI**'
      return `${label}\n${m.content}`
    })
    .join('\n\n---\n\n')

  navigator.clipboard.writeText(text).catch(() => {
    // 静默失败
  })
}
</script>

<template>
  <div class="chat-page">
    <!-- 顶部功能区 -->
    <div class="chat-header">
      <h1 class="chat-title">对话</h1>
      <div class="header-actions">
        <CustomSelect
          v-model="selectedProfileId"
          :options="profileOptions"
          placeholder="选择模型"
        />
        <button
          v-if="messages.length > 0"
          class="header-btn"
          title="复制对话"
          @click="copyConversation"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
        </button>
        <button
          v-if="messages.length > 0"
          class="header-btn"
          title="清空对话"
          @click="clear"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
            <path d="M10 11v6" />
            <path d="M14 11v6" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 无 Profile 提示 -->
    <div v-if="settingsStore.profilesLoaded && settingsStore.profiles.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <p class="empty-title">尚未配置 LLM 模型</p>
      <p class="empty-desc">请先在设置中添加至少一个 LLM 配置</p>
      <button class="empty-action" @click="settingsStore.openSettingsModal('llm')">
        前往设置
      </button>
    </div>

    <!-- 消息列表 -->
    <div
      v-else
      ref="messagesContainer"
      class="messages-container"
    >
      <!-- 空对话引导 -->
      <div v-if="messages.length === 0" class="welcome">
        <div class="welcome-icon">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <p class="welcome-title">开始对话</p>
        <p class="welcome-desc">输入消息，与 AI 模型自由交流</p>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="message-row"
        :class="msg.role"
      >
        <div class="message-bubble">
          <template v-if="msg.role === 'assistant'">
            <MarkdownRenderer v-if="msg.content" :content="msg.content" />
            <span v-else-if="isStreaming && index === messages.length - 1" class="typing-cursor" />
          </template>
          <template v-else>
            <p class="user-text">{{ msg.content }}</p>
          </template>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="error" class="error-banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span>{{ error }}</span>
      </div>
    </div>

    <!-- 输入区域 -->
    <div v-if="settingsStore.profiles.length > 0" class="input-area">
      <div class="input-wrapper">
        <textarea
          v-model="inputText"
          class="input-field"
          placeholder="输入消息...（Enter 发送，Shift+Enter 换行）"
          rows="1"
          :disabled="isStreaming"
          @keydown="handleKeydown"
        />
        <button
          v-if="isStreaming"
          class="send-btn stop-btn"
          title="停止生成"
          @click="cancel"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        </button>
        <button
          v-else
          class="send-btn"
          :disabled="!inputText.trim()"
          title="发送"
          @click="handleSend"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 800px;
  margin: 0 auto;
}

/* ─── 顶部功能区 ────────────────────────────────────────── */

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) 0;
  border-bottom: 1px solid var(--color-rule);
  flex-shrink: 0;
}

.chat-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}


.header-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.header-btn:hover {
  color: var(--color-text);
  background: var(--color-accent-soft);
}

/* ─── 空状态 ────────────────────────────────────────────── */

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  color: var(--color-text-muted);
}

.empty-icon {
  opacity: 0.4;
}

.empty-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 0;
}

.empty-desc {
  font-size: 14px;
  margin: 0;
}

.empty-action {
  margin-top: var(--space-sm);
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-bg-surface);
  background: var(--color-accent);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.empty-action:hover {
  background: var(--color-accent-hover);
}

/* ─── 消息列表 ──────────────────────────────────────────── */

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg) 0;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-3xl) 0;
  color: var(--color-text-muted);
}

.welcome-icon {
  opacity: 0.3;
  margin-bottom: var(--space-md);
}

.welcome-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 0 0 6px;
}

.welcome-desc {
  font-size: 14px;
  margin: 0;
}

/* ─── 消息气泡 ──────────────────────────────────────────── */

.message-row {
  display: flex;
  margin-bottom: var(--space-md);
  animation: fadeSlideIn 200ms ease-out;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
}

.message-row.user .message-bubble {
  background: var(--color-accent);
  color: var(--color-bg-surface);
  border-bottom-right-radius: var(--radius-sm);
}

.message-row.assistant .message-bubble {
  background: var(--color-bg-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: var(--radius-sm);
}

.user-text {
  margin: 0;
  white-space: pre-wrap;
}

/* ─── 打字光标 ──────────────────────────────────────────── */

.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--color-accent);
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ─── 错误提示 ──────────────────────────────────────────── */

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px 14px;
  margin: var(--space-md) 0;
  background: var(--color-error-bg);
  color: var(--color-error);
  border-radius: var(--radius-md);
  font-size: 13px;
}

/* ─── 输入区域 ──────────────────────────────────────────── */

.input-area {
  flex-shrink: 0;
  padding: var(--space-md) 0;
  border-top: 1px solid var(--color-rule);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  padding: 8px 12px;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: border-color var(--transition-fast);
}

.input-wrapper:focus-within {
  border-color: var(--color-accent);
}

.input-field {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--color-text);
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  min-height: 24px;
  max-height: 120px;
  padding: 4px 0;
}

.input-field::placeholder {
  color: var(--color-text-light);
}

.input-field:disabled {
  opacity: 0.6;
}

.send-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  color: var(--color-bg-surface);
  background: var(--color-accent);
  transition: background var(--transition-fast), opacity var(--transition-fast);
}

.send-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.stop-btn {
  background: var(--color-error);
}

.stop-btn:hover {
  background: var(--color-error);
  opacity: 0.85;
}

/* ─── 响应式 ────────────────────────────────────────────── */

@media (max-width: 768px) {
  .chat-header {
    padding: var(--space-sm) 0;
  }

  .message-bubble {
    max-width: 92%;
  }
}
</style>
