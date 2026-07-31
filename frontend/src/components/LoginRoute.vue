<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import LoginPage from './LoginPage.vue'

const route = useRoute()
const router = useRouter()

async function afterLogin() {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/overview'
  await router.replace(redirect)
}
</script>

<template>
  <LoginPage @authenticated="afterLogin" />
</template>
