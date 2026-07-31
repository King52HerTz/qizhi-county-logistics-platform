import { createRouter, createWebHistory } from 'vue-router'
import { getSessionRole, hasSession } from './services/api'

const PlatformShell = () => import('./App.vue')
const LoginRoute = () => import('./components/LoginRoute.vue')
const RegisterRoute = () => import('./components/RegisterRoute.vue')

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/overview' },
    { path: '/login', name: 'login', component: LoginRoute, meta: { public: true } },
    { path: '/register', name: 'register', component: RegisterRoute, meta: { public: true } },
    { path: '/overview', name: 'overview', component: PlatformShell },
    { path: '/dispatch', name: 'dispatch', component: PlatformShell },
    { path: '/events', name: 'events', component: PlatformShell },
    { path: '/execution', name: 'execution', component: PlatformShell },
    { path: '/experiments', name: 'experiments', component: PlatformShell },
    { path: '/history', name: 'history', component: PlatformShell },
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
  if (to.meta.public) {
    return hasSession() && (to.name === 'login' || to.name === 'register')
      ? { name: 'overview' }
      : true
  }
  if (!hasSession()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(getSessionRole())) {
    return { name: 'overview' }
  }
  if (to.name === 'settings' && !to.params.section) {
    return { name: 'settings', params: { section: 'ai' } }
  }
  if (to.name === 'masterData' && !to.params.section) {
    return { name: 'masterData', params: { section: 'orders' } }
  }
  return true
})
