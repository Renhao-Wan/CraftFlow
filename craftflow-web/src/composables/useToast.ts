import { reactive } from 'vue'

export type ToastType = 'info' | 'success' | 'warning' | 'error'

export interface Toast {
  id: number
  type: ToastType
  message: string
  duration: number
}

const MAX_TOASTS = 5

let nextId = 0

const toasts = reactive<Toast[]>([])

function remove(id: number): void {
  const index = toasts.findIndex((t) => t.id === id)
  if (index !== -1) toasts.splice(index, 1)
}

function show(message: string, type: ToastType = 'info', duration = 4000): number {
  const id = nextId++
  if (toasts.length >= MAX_TOASTS) {
    toasts.shift()
  }
  toasts.push({ id, type, message, duration })
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
  return id
}

export function useToast() {
  return {
    toasts,
    show,
    remove,
    info: (message: string, duration?: number) => show(message, 'info', duration),
    success: (message: string, duration?: number) => show(message, 'success', duration),
    warning: (message: string, duration?: number) => show(message, 'warning', duration),
    error: (message: string, duration?: number) => show(message, 'error', duration),
  }
}
