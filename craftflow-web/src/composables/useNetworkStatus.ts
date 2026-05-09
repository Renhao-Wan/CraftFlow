import { ref, onMounted, onUnmounted } from 'vue'
import { useToast } from './useToast'

const isOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)

let initialized = false

function handleOnline(): void {
  isOnline.value = true
}

function handleOffline(): void {
  isOnline.value = false
}

export function useNetworkStatus() {
  if (!initialized) {
    initialized = true
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
  }

  const toast = useToast()

  onMounted(() => {
    if (!isOnline.value) {
      toast.warning('网络连接已断开，请检查网络', 0)
    }
  })

  onUnmounted(() => {
    // no-op: 全局监听器保持运行
  })

  return { isOnline }
}
