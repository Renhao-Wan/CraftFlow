<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const sidebarOpen = ref(false)

const navItems = [
  { label: '创作', path: '/creation', icon: 'pen' },
  { label: '润色', path: '/polishing', icon: 'sparkle' },
  { label: '历史', path: '/history', icon: 'clock' },
]

const currentPath = computed(() => route.path)

function isActive(path: string): boolean {
  return currentPath.value === path || currentPath.value.startsWith(path + '/')
}

function toggleSidebar(): void {
  sidebarOpen.value = !sidebarOpen.value
}

function closeSidebar(): void {
  sidebarOpen.value = false
}

function navigateTo(path: string): void {
  router.push(path)
  closeSidebar()
}
</script>

<template>
  <!-- Mobile overlay -->
  <div
    v-if="sidebarOpen"
    class="sidebar-overlay"
    @click="closeSidebar"
  />

  <!-- Mobile header (visible < 768px) -->
  <header class="mobile-header">
    <button class="hamburger" aria-label="菜单" @click="toggleSidebar">
      <span class="hamburger-line" />
      <span class="hamburger-line" />
      <span class="hamburger-line" />
    </button>
    <span class="mobile-logo" @click="navigateTo('/')">CraftFlow</span>
  </header>

  <!-- Sidebar -->
  <aside class="app-sidebar" :class="{ open: sidebarOpen }">
    <div class="sidebar-inner">
      <!-- Logo -->
      <div class="sidebar-logo" @click="navigateTo('/')">
        <span class="logo-text">CraftFlow</span>
        <span class="logo-tagline">创作平台</span>
      </div>

      <!-- Divider -->
      <div class="sidebar-divider" />

      <!-- Navigation -->
      <nav class="sidebar-nav">
        <button
          v-for="item in navItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="navigateTo(item.path)"
        >
          <span class="nav-indicator" />
          <span class="nav-icon">
            <!-- Pen icon -->
            <svg v-if="item.icon === 'pen'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
            <!-- Sparkle icon -->
            <svg v-else-if="item.icon === 'sparkle'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3z" />
            </svg>
            <!-- Clock icon -->
            <svg v-else-if="item.icon === 'clock'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>

      <!-- Footer -->
      <div class="sidebar-footer">
        <div class="sidebar-divider" />
        <div class="footer-info">
          <span class="footer-version">v0.1.0</span>
          <span class="footer-dot">&middot;</span>
          <span class="footer-status">AI 就绪</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* --- Mobile Header --- */
.mobile-header {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height);
  background: var(--color-bg-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 0 var(--space-md);
  align-items: center;
  gap: var(--space-md);
  z-index: 200;
}

.hamburger {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 36px;
  height: 36px;
  padding: 6px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.hamburger:hover {
  background: var(--color-accent-soft);
}

.hamburger-line {
  display: block;
  width: 20px;
  height: 2px;
  background: var(--color-text);
  border-radius: 1px;
  transition: transform var(--transition-fast);
}

.mobile-logo {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
  cursor: pointer;
}

/* --- Overlay --- */
.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 299;
  animation: fadeIn 200ms ease;
}

/* --- Sidebar --- */
.app-sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--color-bg-sidebar);
  z-index: 300;
  overflow: hidden;
  /* Subtle noise texture via SVG data URI */
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
  background-size: 128px 128px;
  box-shadow: var(--shadow-sidebar);
}

.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-lg) 0;
  overflow-y: auto;
}

/* --- Logo --- */
.sidebar-logo {
  padding: 0 var(--space-lg) var(--space-lg);
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.sidebar-logo:hover {
  opacity: 0.85;
}

.logo-text {
  display: block;
  font-family: var(--font-display);
  font-style: italic;
  font-size: 24px;
  font-weight: 600;
  color: #FFFFFF;
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.logo-tagline {
  display: block;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 400;
  color: var(--color-text-sidebar-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 4px;
}

/* --- Divider --- */
.sidebar-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: var(--space-sm) var(--space-lg);
}

/* --- Navigation --- */
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-md) var(--space-sm);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  color: var(--color-text-sidebar-muted);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
  position: relative;
  text-align: left;
  width: 100%;
}

.nav-item:hover {
  color: var(--color-text-sidebar);
  background: var(--color-bg-sidebar-hover);
}

.nav-item.active {
  color: #FFFFFF;
  background: rgba(255, 255, 255, 0.06);
}

.nav-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--color-accent);
  border-radius: 0 2px 2px 0;
  transition: height var(--transition-normal);
}

.nav-item.active .nav-indicator {
  height: 20px;
}

.nav-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  opacity: 0.7;
}

.nav-item.active .nav-icon {
  opacity: 1;
}

.nav-label {
  flex: 1;
}

/* --- Footer --- */
.sidebar-footer {
  margin-top: auto;
  padding-top: var(--space-sm);
}

.footer-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-lg) 0;
  font-size: 11px;
  color: var(--color-text-sidebar-muted);
}

.footer-dot {
  opacity: 0.4;
}

.footer-status {
  color: #4ade80;
}

/* --- Responsive (< 768px) --- */
@media (max-width: 768px) {
  .mobile-header {
    display: flex;
  }

  .sidebar-overlay {
    display: block;
  }

  .app-sidebar {
    transform: translateX(-100%);
    transition: transform var(--transition-slow);
  }

  .app-sidebar.open {
    transform: translateX(0);
  }
}
</style>
