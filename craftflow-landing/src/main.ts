/**
 * CraftFlow Landing Page — Main Entry
 * 主题切换、滚动动画、导航交互
 */

// ============================================
// Theme Toggle
// ============================================

type Theme = 'light' | 'dark' | 'sepia' | 'midnight' | 'frost' | 'rose'

const STORAGE_KEY = 'craftflow-theme'

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  const validThemes: Theme[] = ['light', 'dark', 'sepia', 'midnight', 'frost', 'rose']

  if (stored && validThemes.includes(stored as Theme)) {
    return stored as Theme
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(STORAGE_KEY, theme)

  // Update active state in panel
  const options = document.querySelectorAll<HTMLElement>('.theme-toggle__option')
  options.forEach(option => {
    option.classList.toggle('active', option.dataset.theme === theme)
  })

  // Update screenshot based on theme
  updateScreenshotForTheme(theme)
}

function updateScreenshotForTheme(theme: Theme): void {
  const screenshot = document.querySelector<HTMLImageElement>('.hero__screenshot')
  if (!screenshot) return

  const themeSrcs = screenshot.dataset.themeSrcs
  if (!themeSrcs) return

  try {
    const srcMap = JSON.parse(themeSrcs)
    const newSrc = srcMap[theme] || srcMap['light']

    // Only update if src changed
    if (screenshot.src !== new URL(newSrc, window.location.origin).href) {
      screenshot.src = newSrc
    }
  } catch {
    // Fallback: keep current src
  }
}

function initScreenshotFallback(): void {
  const screenshot = document.querySelector<HTMLImageElement>('.hero__screenshot')
  const fallback = document.querySelector<HTMLElement>('.hero__fallback')

  if (!screenshot || !fallback) return

  // Show fallback if image fails to load
  screenshot.addEventListener('error', () => {
    screenshot.style.display = 'none'
    fallback.classList.add('active')
  })

  // Hide fallback if image loads successfully
  screenshot.addEventListener('load', () => {
    screenshot.style.display = 'block'
    fallback.classList.remove('active')
  })

  // Check if image already failed (cached error)
  if (screenshot.complete && !screenshot.naturalWidth) {
    screenshot.style.display = 'none'
    fallback.classList.add('active')
  }
}

function initThemeToggle(): void {
  const btn = document.getElementById('themeToggleBtn')
  const panel = document.getElementById('themePanel')
  const options = document.querySelectorAll<HTMLElement>('.theme-toggle__option')

  if (!btn || !panel) return

  // Apply initial theme
  const currentTheme = getInitialTheme()
  applyTheme(currentTheme)

  // Toggle panel
  btn.addEventListener('click', (e) => {
    e.stopPropagation()
    panel.classList.toggle('open')
  })

  // Select theme
  options.forEach(option => {
    option.addEventListener('click', () => {
      const theme = option.dataset.theme as Theme
      if (theme) {
        applyTheme(theme)
        panel.classList.remove('open')
      }
    })
  })

  // Close panel on outside click
  document.addEventListener('click', (e) => {
    if (!panel.contains(e.target as Node) && !btn.contains(e.target as Node)) {
      panel.classList.remove('open')
    }
  })
}

// ============================================
// Navbar Scroll Effect
// ============================================

function initNavbarScroll(): void {
  const navbar = document.getElementById('navbar')
  if (!navbar) return

  window.addEventListener('scroll', () => {
    // Add scrolled class when scrolled down
    if (window.scrollY > 50) {
      navbar.classList.add('scrolled')
    } else {
      navbar.classList.remove('scrolled')
    }
  }, { passive: true })
}

// ============================================
// Mobile Menu
// ============================================

function initMobileMenu(): void {
  const hamburger = document.getElementById('navHamburger')
  const menu = document.getElementById('navMenu')

  if (!hamburger || !menu) return

  hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active')
    menu.classList.toggle('open')
  })

  // Close menu on link click
  const links = menu.querySelectorAll('.navbar__link')
  links.forEach(link => {
    link.addEventListener('click', () => {
      hamburger.classList.remove('active')
      menu.classList.remove('open')
    })
  })
}

// ============================================
// Smooth Scroll
// ============================================

function initSmoothScroll(): void {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const href = (e.currentTarget as HTMLAnchorElement).getAttribute('href')
      if (!href || href === '#') return

      e.preventDefault()
      const targetId = href.substring(1)
      const target = document.getElementById(targetId)

      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        })
      }
    })
  })
}

// ============================================
// Scroll Reveal Animation
// ============================================

function initScrollReveal(): void {
  const revealElements = document.querySelectorAll<HTMLElement>('.reveal, .reveal-stagger')

  if (!revealElements.length) return

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible')
        observer.unobserve(entry.target)
      }
    })
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  })

  revealElements.forEach(el => {
    observer.observe(el)
  })
}

// ============================================
// Toast
// ============================================

function showToast(message: string, duration: number = 3000): void {
  const toast = document.getElementById('toast')
  const messageEl = toast?.querySelector('.toast__message')

  if (!toast || !messageEl) return

  messageEl.textContent = message
  toast.classList.add('show')

  setTimeout(() => {
    toast.classList.remove('show')
  }, duration)
}

function initOnlineAccess(): void {
  // Hero 部分的"在线体验"按钮 → 锚点跳转到 #online
  const heroBtn = document.getElementById('onlineAccessBtn')
  if (heroBtn) {
    heroBtn.addEventListener('click', (e) => {
      e.preventDefault()
      const target = document.getElementById('online')
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  }

  // 底部在线体验部分的"立即体验"按钮 → 实际链接跳转
  const altBtn = document.getElementById('onlineAccessBtnAlt')
  if (altBtn) {
    altBtn.addEventListener('click', (e) => {
      e.preventDefault()
      // TODO: 替换为实际的在线体验链接
      // window.open('https://your-online-url.com', '_blank')
      showToast('功能开发中，敬请期待')
    })
  }
}

// ============================================
// Initialize
// ============================================

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle()
  initNavbarScroll()
  initMobileMenu()
  initSmoothScroll()
  initScrollReveal()
  initOnlineAccess()
  initScreenshotFallback()
})
