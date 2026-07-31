<script setup lang="ts">
import { useRouter } from 'vue-router'
import RegisterPage from './RegisterPage.vue'

const router = useRouter()

async function afterRegistration() {
  await router.replace('/overview')
}
</script>

<template>
  <RegisterPage @authenticated="afterRegistration" />
</template>
