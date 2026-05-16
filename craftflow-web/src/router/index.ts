import { createRouter, createWebHashHistory } from 'vue-router'
import { useNavigationStore } from '@/stores/navigation'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/Home.vue'),
    },
    {
      path: '/creation',
      name: 'creation',
      component: () => import('@/views/creation/TaskCreate.vue'),
    },
    {
      path: '/tasks/:taskId',
      name: 'task-detail',
      component: () => import('@/views/creation/TaskDetail.vue'),
      props: true,
    },
    {
      path: '/polishing',
      name: 'polishing',
      component: () => import('@/views/polishing/PolishingCreate.vue'),
    },
    {
      path: '/polishing/:taskId',
      name: 'polishing-result',
      component: () => import('@/views/polishing/PolishingResult.vue'),
      props: true,
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/TaskHistory.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/Chat.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

/** 判断是否为任务详情路由 */
function isDetailRoute(name: string | null | undefined): boolean {
  return name === 'task-detail' || name === 'polishing-result'
}

// 注意：不在路由守卫中取消订阅，保持订阅以继续接收流式内容
// 订阅的取消由 useTaskLifecycle 中的 stop 函数在任务完成/失败时调用

router.afterEach((to) => {
  if (!isDetailRoute(to.name as string)) {
    const navStore = useNavigationStore()
    navStore.clearDetailSource()
  }
})

export default router
