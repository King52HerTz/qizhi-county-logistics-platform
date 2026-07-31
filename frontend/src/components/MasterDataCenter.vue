<script setup lang="ts">
import {
  AlertTriangle, Boxes, CheckCircle2, Clock3, MapPinned, Snowflake, Truck,
} from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDataQualityReport, getMasterDataSummary } from '../services/api'
import type { MasterDataSummary } from '../types/logistics'
import MasterNodes from './MasterNodes.vue'
import MasterOrders from './MasterOrders.vue'
import MasterVehicles from './MasterVehicles.vue'
import DataQualityCenter from './DataQualityCenter.vue'
import SpatialCalibration from './SpatialCalibration.vue'
import '../styles/master-data.css'

type Section = 'orders' | 'vehicles' | 'nodes' | 'spatial' | 'quality'
const route = useRoute()
const router = useRouter()
const summary = ref<MasterDataSummary>({
  order_total: 0,
  pending_orders: 0,
  cold_chain_orders: 0,
  invalid_orders: 0,
  vehicle_total: 0,
  available_vehicles: 0,
  node_total: 0,
  active_nodes: 0,
})
const qualityBlocked = ref(0)
const section = computed(() => String(route.params.section || 'orders') as Section)
const tabs: Array<{ key: Section; label: string }> = [
  { key: 'orders', label: '订单台账' },
  { key: 'vehicles', label: '车辆档案' },
  { key: 'nodes', label: '网点站点' },
  { key: 'spatial', label: '空间校准' },
  { key: 'quality', label: '数据质量' },
]
const summaryCards = computed(() => {
  if (section.value === 'quality') {
    return [
      { label: '待调度订单', value: summary.value.pending_orders, icon: Clock3 },
      { label: '可用车辆', value: summary.value.available_vehicles, icon: Truck },
      { label: '启用网点', value: summary.value.active_nodes, icon: MapPinned },
      { label: '阻断问题', value: qualityBlocked.value, icon: AlertTriangle },
    ]
  }
  if (section.value === 'vehicles') {
    return [
      { label: '车辆总数', value: summary.value.vehicle_total, icon: Truck },
      { label: '可用车辆', value: summary.value.available_vehicles, icon: CheckCircle2 },
      { label: '不可用车辆', value: summary.value.vehicle_total - summary.value.available_vehicles, icon: Clock3 },
      { label: '冷链订单需求', value: summary.value.cold_chain_orders, icon: Snowflake },
    ]
  }
  if (section.value === 'nodes') {
    return [
      { label: '网点总数', value: summary.value.node_total, icon: MapPinned },
      { label: '启用网点', value: summary.value.active_nodes, icon: CheckCircle2 },
      { label: '停用网点', value: summary.value.node_total - summary.value.active_nodes, icon: Clock3 },
      { label: '关联订单', value: summary.value.order_total, icon: Boxes },
    ]
  }
  return [
    { label: '订单总数', value: summary.value.order_total, icon: Boxes },
    { label: '待调度', value: summary.value.pending_orders, icon: Clock3 },
    { label: '冷链订单', value: summary.value.cold_chain_orders, icon: Snowflake },
    { label: '异常数据', value: summary.value.invalid_orders, icon: AlertTriangle },
  ]
})

async function loadSummary() {
  summary.value = await getMasterDataSummary()
  if (section.value === 'quality') {
    qualityBlocked.value = (await getDataQualityReport()).blocked_count
  }
}
function go(next: Section) {
  router.push(`/master-data/${next}`)
}

onMounted(loadSummary)
watch(section, loadSummary)
</script>

<template>
  <section class="master-data-page">
    <header class="master-page-header">
      <div>
        <h1>{{ section === 'spatial' ? '空间数据校准' : '基础数据中心' }}</h1>
        <p>{{ section === 'spatial' ? '统一核验服务网点位置、坐标来源与空间质量' : '统一维护订单、车辆与服务网点，为调度求解提供可信数据' }}</p>
      </div>
    </header>

    <nav class="master-tabs" aria-label="基础数据分类">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="{ active: section === tab.key }"
        @click="go(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div v-if="section !== 'spatial'" class="master-summary">
      <article v-for="card in summaryCards" :key="card.label">
        <span class="summary-icon"><component :is="card.icon" :size="20" /></span>
        <div><small>{{ card.label }}</small><strong>{{ card.value }}</strong></div>
      </article>
    </div>

    <MasterOrders v-if="section === 'orders'" @changed="loadSummary" />
    <MasterVehicles v-else-if="section === 'vehicles'" @changed="loadSummary" />
    <MasterNodes v-else-if="section === 'nodes'" @changed="loadSummary" />
    <SpatialCalibration v-else-if="section === 'spatial'" />
    <DataQualityCenter v-else @changed="loadSummary" />
  </section>
</template>
