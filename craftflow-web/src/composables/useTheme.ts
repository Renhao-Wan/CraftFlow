import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark' | 'sepia' | 'midnight' | 'frost' | 'rose'

const STORAGE_KEY = 'craftflow-theme'

const theme = ref<Theme>(getInitialTheme())

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'sepia' || stored === 'midnight' || stored === 'frost' || stored === 'rose') {
    return stored
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(newTheme: Theme): void {
  document.documentElement.setAttribute('data-theme', newTheme)
  localStorage.setItem(STORAGE_KEY, newTheme)
}

// Apply theme immediately on load
applyTheme(theme.value)

// Watch for changes
watch(theme, (newTheme) => {
  applyTheme(newTheme)
})

export function useTheme() {
  function toggleTheme(): void {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  function setTheme(newTheme: Theme): void {
    theme.value = newTheme
  }

  return {
    theme,
    toggleTheme,
    setTheme,
  }
}
