import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { wsClient } from '@/api/wsClient'
import { useTheme } from '@/composables/useTheme'
import './styles/variables.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')

// 应用挂载后初始化 WebSocket 连接
wsClient.connect()
