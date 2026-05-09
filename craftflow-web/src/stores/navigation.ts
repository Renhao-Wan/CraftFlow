import { ref } from 'vue'
import { defineStore } from 'pinia'

export type NavSource = 'creation' | 'polishing' | 'history'

export const useNavigationStore = defineStore('navigation', () => {
  const detailSource = ref<NavSource | null>(null)

  function setDetailSource(source: NavSource): void {
    detailSource.value = source
  }

  function clearDetailSource(): void {
    detailSource.value = null
  }

  return { detailSource, setDetailSource, clearDetailSource }
})
