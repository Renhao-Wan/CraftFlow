import { createRouter, createWebHashHistory } from 'vue-router'

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
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

export default router
