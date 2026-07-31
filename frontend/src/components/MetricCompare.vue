<script setup lang="ts">
import { ArrowRight, Clock3, Route as RouteIcon, Truck, WalletCards } from '@lucide/vue'
import type { Metrics } from '../types/logistics'

defineProps<{ baseline: Metrics; optimized: Metrics }>()

const rows = [
  { key: 'distance_km', label: '总里程', unit: 'km', icon: RouteIcon },
  { key: 'empty_distance_rate', label: '空驶率', unit: '%', icon: Clock3 },
  { key: 'estimated_cost_cny', label: '配送成本', unit: '元', icon: WalletCards },
  { key: 'vehicles_used', label: '启用车辆', unit: '辆', icon: Truck },
] as const
</script>

<template>
  <div class="compare">
    <div v-for="row in rows" :key="row.key" class="metric">
      <component :is="row.icon" :size="17" />
      <div>
        <span>{{ row.label }}</span>
        <div class="numbers">
          <b>{{ baseline[row.key] }}</b>
          <ArrowRight :size="14" />
          <strong>{{ optimized[row.key] }}</strong>
          <small>{{ row.unit }}</small>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.compare { display:grid; grid-template-columns:repeat(4,1fr); gap:10px }
.metric { display:flex; gap:10px; align-items:center; padding:12px 14px; border:1px solid #e7ebe7; border-radius:12px; color:#6c756f; background:#fff }
.metric > svg { color:#1f7a4b }
.metric span { font-size:12px }
.numbers { display:flex; align-items:baseline; gap:7px; margin-top:3px }
.numbers b { color:#8b928e; font-size:14px; text-decoration:line-through; font-weight:500 }
.numbers strong { color:#123c2b; font-size:20px }
.numbers small { font-size:11px }
@media (max-width: 1000px) { .compare { grid-template-columns:repeat(2,1fr) } }
@media (max-width: 760px) { .compare { grid-template-columns:1fr } .metric { min-width:0 } }
</style>
