import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

import Layout from '../views/Layout.vue'
import Login from '../views/Login.vue'
import ImageDetect from '../views/ImageDetect.vue'
import VideoDetect from '../views/VideoDetect.vue'
import CameraDetect from '../views/CameraDetect.vue'
import HistoryReview from '../views/HistoryReview.vue'
import ModelManagement from '../views/ModelManagement.vue'
import MetricsDashboard from '../views/MetricsDashboard.vue'
import UserManagement from '../views/admin/UserManagement.vue'
import SystemLogs from '../views/admin/SystemLogs.vue'
import ScreenDashboard from '../views/ScreenDashboard.vue'
import ViolationAnalysis from '../views/ViolationAnalysis.vue'
import CitizenPortal from '../views/CitizenPortal.vue'

const routes = [
  {
    path: '/screen',
    name: 'ScreenDashboard',
    component: ScreenDashboard
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/citizen',
    name: 'CitizenPortal',
    component: CitizenPortal
  },
  {
    path: '/',
    component: Layout,
    redirect: '/metrics', // 默认进入指标展示页面，立即查看参考图同款效果！
    children: [
      {
        path: 'image',
        name: 'ImageDetect',
        component: ImageDetect
      },
      {
        path: 'video',
        name: 'VideoDetect',
        component: VideoDetect
      },
      {
        path: 'camera',
        name: 'CameraDetect',
        component: CameraDetect
      },
      {
        path: 'history',
        name: 'HistoryReview',
        component: HistoryReview
      },
      {
        path: 'model',
        name: 'ModelManagement',
        component: ModelManagement
      },
      {
        path: 'metrics',
        name: 'MetricsDashboard',
        component: MetricsDashboard
      },
      {
        path: 'analysis',
        name: 'ViolationAnalysis',
        component: ViolationAnalysis
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: UserManagement
      },
      {
        path: 'admin/logs',
        name: 'AdminLogs',
        component: SystemLogs
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // 群众端与执法后台互不通行：
  //   · 未登录进 /citizen → 去登录页选"市民"身份
  //   · 执法账号进 /citizen → 拒回后台（民警不需要看市民视图，权限边界要清楚）
  //   · 市民账号进后台任意页 → 拒回自己家（台账是执法侧全量视图，市民无权访问）
  if (to.path === '/citizen') {
    if (!authStore.isLoggedIn) return next('/login')
    if (!authStore.isCitizen) return next('/history')
    return next()
  }

  if (to.path !== '/login' && !authStore.isLoggedIn) {
    return next('/login')
  }
  if (authStore.isCitizen && to.path !== '/login') {
    return next('/citizen')
  }
  next()
})

export default router
