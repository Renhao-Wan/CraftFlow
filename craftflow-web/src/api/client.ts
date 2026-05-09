import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ApiError, type ErrorResponse } from './types/errors'
import { useToast } from '@/composables/useToast'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：预留 token 注入
client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // TODO: 认证启用后在此注入 Authorization header
  return config
})

// 响应拦截器：统一提取 data，错误抛出 ApiError
client.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error) => {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status ?? 0
      const data = error.response?.data as ErrorResponse | undefined
      const message = data?.message ?? error.message ?? '请求失败'

      const toast = useToast()

      if (!error.response) {
        toast.error('网络连接失败，请检查网络后重试', 6000)
        throw new ApiError('网络连接失败', 0, data)
      }

      switch (status) {
        case 401:
          toast.warning('登录已过期，请重新登录')
          break
        case 403:
          toast.error('没有权限执行此操作')
          break
        case 500:
        case 502:
        case 503:
          toast.error('服务器暂时不可用，请稍后重试')
          break
      }

      throw new ApiError(message, status, data)
    }
    throw error
  },
)

export default client
