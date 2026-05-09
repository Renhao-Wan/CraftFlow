<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found-page">
    <div class="not-found-content">
      <h1 class="not-found-code">404</h1>
      <div class="not-found-rule" />
      <p class="not-found-text">页面不存在</p>
      <p class="not-found-desc">请检查 URL 是否正确，或返回首页。</p>
      <div class="not-found-actions">
        <button class="action-btn primary" @click="router.push('/')">返回首页</button>
        <button class="action-btn" @click="router.push({ name: 'history' })">查看历史</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.not-found-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.not-found-content {
  text-align: center;
}

.not-found-code {
  font-family: var(--font-display);
  font-size: 96px;
  font-weight: 700;
  color: var(--color-border);
  margin: 0 0 16px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.not-found-rule {
  width: 32px;
  height: 2px;
  background: var(--color-accent);
  margin: 0 auto 20px;
}

.not-found-text {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 8px;
}

.not-found-desc {
  font-size: 15px;
  color: var(--color-text-muted);
  margin: 0 0 var(--space-lg);
}

.not-found-actions {
  display: flex;
  gap: var(--space-md);
  justify-content: center;
  flex-wrap: wrap;
}

.action-btn {
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  border-color: var(--color-text-muted);
}

.action-btn.primary {
  color: #fff;
  background: var(--color-accent);
  border-color: var(--color-accent);
}

.action-btn.primary:hover {
  background: var(--color-accent-hover);
}
</style>
