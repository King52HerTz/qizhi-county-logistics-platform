<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AIConnectionsSettings from './AIConnectionsSettings.vue'
import AuditLogs from './AuditLogs.vue'
import MapConnectionsSettings from './MapConnectionsSettings.vue'
import SecurityPolicy from './SecurityPolicy.vue'
import UserGovernance from './UserGovernance.vue'

const route = useRoute()
const router = useRouter()
const section = computed(() => String(route.params.section || 'ai'))
const tabs = [
  { key: 'ai', label: 'AI 服务' },
  { key: 'map', label: '地图服务' },
  { key: 'users', label: '用户与权限' },
  { key: 'audit', label: '审计日志' },
  { key: 'security', label: '安全策略' },
]
</script>

<template>
  <section class="system-settings">
    <nav class="settings-tabs" aria-label="系统设置">
      <button v-for="tab in tabs" :key="tab.key" :class="{ active: section === tab.key }" @click="router.push(`/settings/${tab.key}`)">{{ tab.label }}</button>
    </nav>
    <AIConnectionsSettings v-if="section === 'ai'" />
    <MapConnectionsSettings v-else-if="section === 'map'" />
    <UserGovernance v-else-if="section === 'users'" />
    <AuditLogs v-else-if="section === 'audit'" />
    <SecurityPolicy v-else />
  </section>
</template>

<style scoped>
.system-settings{display:flex;flex-direction:column;gap:22px}.settings-tabs{display:flex;gap:4px;border-bottom:1px solid #dce4df}.settings-tabs button{position:relative;height:44px;padding:0 16px;border:0;background:transparent;color:#6d7972;font-size:13px;font-weight:750;cursor:pointer}.settings-tabs button:hover{color:#176e49}.settings-tabs button.active{color:#116c47}.settings-tabs button.active::after{content:"";position:absolute;left:13px;right:13px;bottom:-1px;height:2px;background:#12744a}
.settings-tabs{flex-direction:row}
</style>
