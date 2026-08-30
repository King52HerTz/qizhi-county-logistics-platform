<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import LoginPage from './LoginPage.vue'
import type { TokenResponse } from '../types/logistics'

const route = useRoute()
const router = useRouter()

async function afterLogin(session: TokenResponse) {
  const fallback = session.role === 'user' ? '/my-orders' : session.role === 'driver' ? '/execution' : '/overview'
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : fallback
  await router.replace(redirect)
}
</script>

<template>
  <LoginPage @authenticated="afterLogin" />
</template>
