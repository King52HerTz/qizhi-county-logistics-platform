import { createRouter, createWebHistory } from 'vue-router'
import { getSessionRole, hasSession } from './services/api'

const PlatformShell = () => import('./App.vue')
const LoginRoute = () => import('./components/LoginRoute.vue')
const RegisterRoute = () => import('./components/RegisterRoute.vue')
const UserOrderRoute = () => import('./components/UserOrderRoute.vue')

function homeForRole(role: string) {
  return role === 'user' ? '/my-orders' : role === 'driver' ? '/execution' : '/overview'
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/overview' },
    { path: '/login', name: 'login', component: LoginRoute, meta: { public: true } },
    { path: '/register', name: 'register', component: RegisterRoute, meta: { public: true } },
    { path: '/overview', name: 'overview', component: PlatformShell, meta: { roles: ['admin', 'dispatcher', 'driver', 'viewer'] } },
    { path: '/dispatch', name: 'dispatch', component: PlatformShell, meta: { roles: ['admin', 'dispatcher'] } },
    { path: '/events', name: 'events', component: PlatformShell, meta: { roles: ['admin', 'dispatcher'] } },
    { path: '/execution', name: 'execution', component: PlatformShell, meta: { roles: ['admin', 'dispatcher', 'driver'] } },
    { path: '/cold-chain', name: 'coldChain', component: PlatformShell, meta: { roles: ['admin', 'dispatcher'] } },
    { path: '/cold-monitor', name: 'coldMonitor', component: PlatformShell, meta: { roles: ['admin', 'dispatcher'] } },
    { path: '/experiments', name: 'experiments', component: PlatformShell, meta: { roles: ['admin', 'dispatcher'] } },
    { path: '/history', name: 'history', component: PlatformShell, meta: { roles: ['admin', 'dispatcher', 'driver', 'viewer'] } },
    {
      path: '/order-requests',
      name: 'orderRequests',
      component: PlatformShell,
      meta: { roles: ['admin'] },
    },
    {
      path: '/my-orders',
      name: 'myOrders',
      component: UserOrderRoute,
      meta: { roles: ['user'] },
    },
    {
      path: '/readiness',
      name: 'readiness',
      component: PlatformShell,
      meta: { roles: ['admin', 'dispatcher'] },
    },
    {
      path: '/master-data/:section(orders|vehicles|nodes|spatial|quality)?',
      name: 'masterData',
      component: PlatformShell,
      meta: { roles: ['admin', 'dispatcher'] },
    },
    {
      path: '/scenarios',
      name: 'scenarios',
      component: PlatformShell,
      meta: { roles: ['admin'] },
    },
    {
      path: '/settings/:section(ai|map|users|audit|security)?',
      name: 'settings',
      component: PlatformShell,
      meta: { roles: ['admin'] },
    },
    { path: '/:pathMatch(.*)*', redirect: '/overview' },
  ],
})

router.beforeEach((to) => {
  if (to.path === '/') return homeForRole(getSessionRole())
  if (to.meta.public) {
    return hasSession() && (to.name === 'login' || to.name === 'register')
      ? homeForRole(getSessionRole())
      : true
  }
  if (!hasSession()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(getSessionRole())) {
    return homeForRole(getSessionRole())
  }
  if (to.name === 'settings' && !to.params.section) {
    return { name: 'settings', params: { section: 'ai' } }
  }
  if (to.name === 'masterData' && !to.params.section) {
    return { name: 'masterData', params: { section: 'orders' } }
  }
  return true
})
