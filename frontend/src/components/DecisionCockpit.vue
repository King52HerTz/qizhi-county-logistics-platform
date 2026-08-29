<script setup lang="ts">
import {
  AlertTriangle, ArrowRight, CircleCheckBig, Clock3, Navigation,
  Route, Snowflake, Sparkles, Truck, TrendingUp,
} from '@lucide/vue'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ProfessionalCountyMap from './ProfessionalCountyMap.vue'
import type {
  DemandForecast, OptimizeResult, QidongReferenceSummary, RoutingStatus, Scenario,
} from '../types/logistics'

const props = defineProps<{
  scenario: Scenario
  result: OptimizeResult
  forecast: DemandForecast
  routingStatus?: RoutingStatus
  referenceSummary?: QidongReferenceSummary
  busy?: boolean
}>()
const emit = defineEmits<{ dispatch: [] }>()

echarts.use([
  BarChart, LineChart, GridComponent, LegendComponent, MarkLineComponent,
  TooltipComponent, CanvasRenderer,
])

const forecastElement = ref<HTMLDivElement>()
const rankingElement = ref<HTMLDivElement>()
let forecastChart: ECharts | undefined
let rankingChart: ECharts | undefined

const dateLabel = (date: string) =>
  new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(new Date(`${date}T00:00:00`))

const routingLabel = computed(() => {
  if (props.result.routing.source === 'osrm') return 'OSRM'
  return props.result.routing.fallback_used ? '估算回退' : '离线估算'
})
const riskCopy = computed(() => ({
  low: '运力充足',
  medium: '关注峰值',
  high: '提前增援',
}[props.forecast.risk_level]))
const totalWeight = computed(() =>
  props.scenario.orders.reduce((sum, order) => sum + order.weight_kg, 0) / 1000)
const saving = computed(() =>
  Math.max(0, Math.round(
    props.result.baseline_metrics.estimated_cost_cny - props.result.metrics.estimated_cost_cny,
  )))
const forecastState = computed(() => {
  if (props.forecast.fallback_used) return '统计基线'
  return props.forecast.validation_mae_tons == null ? '模型预测' : '模型已验证'
})
const referenceCandidates = computed(() =>
  props.referenceSummary?.candidates.filter(item => item.candidate_type === 'core').slice(0, 3) ?? [])
const referenceQualityLabel = computed(() => {
  const quality = props.referenceSummary?.coordinate_quality
  if (!quality) return ''
  return quality.status === 'verified' ? '坐标已核验' : `${quality.outside_bounds} 个点待核验`
})

function renderCharts() {
  if (!forecastElement.value || !rankingElement.value) return
  forecastChart ??= echarts.init(forecastElement.value)
  rankingChart ??= echarts.init(rankingElement.value)
  const actual = props.forecast.points.filter(
    item => typeof item.actual_tons === 'number' && Number.isFinite(item.actual_tons),
  )
  const predicted = props.forecast.points.filter(
    item => typeof item.forecast_tons === 'number' && Number.isFinite(item.forecast_tons),
  )
  const dates = [...new Set(props.forecast.points.map(item => item.date))]
  const actualMap = new Map(actual.map(item => [item.date, item.actual_tons]))
  const predictedMap = new Map(predicted.map(item => [item.date, item.forecast_tons]))
  const lowerMap = new Map(
    predicted
      .filter(item => typeof item.lower_tons === 'number')
      .map(item => [item.date, item.lower_tons as number]),
  )
  const upperMap = new Map(
    predicted
      .filter(item => typeof item.upper_tons === 'number')
      .map(item => [item.date, item.upper_tons as number]),
  )
  const todayForecastDate = predicted[0]?.date
  forecastChart.setOption({
    animationDuration: 450,
    grid: { left: 38, right: 16, top: 48, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,.98)',
      borderColor: '#d9e2dc',
      borderWidth: 1,
      padding: [9, 11],
      textStyle: { color: '#23372c', fontSize: 11 },
      formatter: (params: any[]) => {
        const meaningful = params.filter(
          item => ['实际需求', '预测需求'].includes(item.seriesName)
            && typeof item.value === 'number'
            && Number.isFinite(item.value),
        )
        if (!meaningful.length) return ''
        const rows = meaningful.map(
          item => `<div style="display:flex;justify-content:space-between;gap:20px;margin-top:6px">
            <span>${item.marker}${item.seriesName}</span>
            <b>${Number(item.value).toFixed(2)} 吨</b>
          </div>`,
        ).join('')
        return `<strong>${params[0]?.axisValueLabel ?? ''}</strong>${rows}`
      },
    },
    legend: {
      top: 4, right: 12, itemWidth: 17, itemHeight: 3, icon: 'roundRect',
      textStyle: { color: '#65746c', fontSize: 10 },
      data: ['实际需求', '预测需求'],
    },
    xAxis: {
      type: 'category', data: dates.map(dateLabel),
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#dce4df' } },
      axisTick: { show: false }, axisLabel: { color: '#7d8a83', fontSize: 9 },
    },
    yAxis: {
      type: 'value', splitNumber: 4, min: 0, name: '吨',
      nameTextStyle: { color: '#8a9690', fontSize: 9, padding: [0, 0, 0, -24] },
      axisLabel: { color: '#7d8a83', fontSize: 9 },
      splitLine: { lineStyle: { color: '#edf1ee', type: 'dashed' } },
    },
    series: [
      {
        name: '预测下界', type: 'line', stack: 'confidence', symbol: 'none',
        data: dates.map(date => lowerMap.get(date) ?? null),
        lineStyle: { opacity: 0 },
        areaStyle: { opacity: 0 },
        tooltip: { show: false },
        silent: true,
      },
      {
        name: '预测区间', type: 'line', stack: 'confidence', symbol: 'none',
        data: dates.map((date) => {
          const lower = lowerMap.get(date)
          const upper = upperMap.get(date)
          return lower === undefined || upper === undefined ? null : Math.max(0, upper - lower)
        }),
        lineStyle: { opacity: 0 },
        areaStyle: { color: 'rgba(40,120,208,.18)' },
        tooltip: { show: false },
        silent: true,
      },
      {
        name: '实际需求', type: 'line', smooth: 0.28, symbolSize: 7,
        data: dates.map(date => actualMap.get(date) ?? null),
        connectNulls: false,
        lineStyle: { color: '#17834f', width: 2.5 },
        itemStyle: { color: '#fff', borderColor: '#17834f', borderWidth: 2.5 },
      },
      {
        name: '预测需求', type: 'line', smooth: 0.28, symbolSize: 6,
        data: dates.map(date => predictedMap.get(date) ?? null),
        connectNulls: false,
        lineStyle: { color: '#2878d0', width: 2.5, type: 'dashed' },
        itemStyle: { color: '#fff', borderColor: '#2878d0', borderWidth: 2 },
        markLine: todayForecastDate ? {
          symbol: 'none',
          silent: true,
          label: {
            show: true, formatter: '今天', position: 'insideEndTop',
            color: '#68776f', fontSize: 9,
          },
          lineStyle: { color: '#aeb9b3', width: 1, type: 'dashed' },
          data: [{ xAxis: dateLabel(todayForecastDate) }],
        } : undefined,
      },
    ],
  })
  const ranking = props.forecast.township_ranking.slice(0, 6).reverse()
  rankingChart.setOption({
    animationDuration: 500,
    grid: { left: 72, right: 22, top: 7, bottom: 8 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (value: unknown) => `${value} 吨` },
    xAxis: { type: 'value', show: false },
    yAxis: {
      type: 'category', data: ranking.map(item => item.node_name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#526159', fontSize: 10 },
    },
    series: [{
      type: 'bar', data: ranking.map(item => item.demand_tons), barWidth: 7,
      itemStyle: { color: '#17834f', borderRadius: [0, 5, 5, 0] },
      label: {
        show: true, position: 'right', color: '#607067', fontSize: 9,
        formatter: ({ value }: { value: number }) => `${value.toFixed(2)}t`,
      },
    }],
  })
}

function resizeCharts() {
  forecastChart?.resize()
  rankingChart?.resize()
}

watch(() => props.forecast, () => nextTick(renderCharts), { deep: true })
onMounted(() => {
  renderCharts()
  window.addEventListener('resize', resizeCharts)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  forecastChart?.dispose()
  rankingChart?.dispose()
})
</script>

<template>
  <div class="cockpit">
    <div class="metric-rail">
      <div><span class="metric-icon green"><TrendingUp :size="21" /></span><p><small>今日预测需求</small><strong>{{ forecast.today_forecast_tons.toFixed(1) }}<i>吨</i></strong></p></div>
      <div><span class="metric-icon green"><Truck :size="21" /></span><p><small>建议运力</small><strong>{{ forecast.recommended_vehicles }}<i>辆</i></strong></p></div>
      <div><span class="metric-icon amber"><Route :size="21" /></span><p><small>路网矩阵</small><strong class="amber-copy">{{ routingLabel }}</strong></p></div>
      <div><span class="metric-icon blue"><Clock3 :size="21" /></span><p><small>预测准时率</small><strong>{{ result.metrics.on_time_rate.toFixed(1) }}<i>%</i></strong></p></div>
    </div>

    <div class="cockpit-main">
      <aside class="analytics-rail">
        <section class="cockpit-panel forecast-panel">
          <div class="panel-heading"><div><h2>未来7日需求预测</h2><p>{{ forecast.method }} · {{ forecast.training_samples }} 个真实样本</p></div><span :class="{ fallback: forecast.fallback_used }">{{ forecastState }}</span></div>
          <div ref="forecastElement" class="forecast-chart" />
        </section>
        <section class="cockpit-panel ranking-panel">
          <div class="panel-heading"><div><h2>乡镇需求排行</h2><p>当前场景订单 · 吨</p></div></div>
          <div ref="rankingElement" class="ranking-chart" />
        </section>
      </aside>

      <section class="cockpit-panel map-panel">
        <div class="panel-heading map-heading">
          <div><h2>县域配送路网态势</h2><p>{{ result.routes.length }} 条优化线路 · {{ result.routing.coordinate_count }} 个矩阵坐标</p></div>
          <span class="live-state"><i /> 引擎在线</span>
        </div>
          <ProfessionalCountyMap :scenario="scenario" :result="result" compact />
        <div class="map-source">
          <Navigation :size="14" />
          <span>{{ result.routing.source === 'osrm' ? 'OSRM 真实路网矩阵' : '县乡道路离线估算矩阵' }}</span>
          <b v-if="result.routing.cache_hit">缓存命中</b>
        </div>
      </section>

      <aside class="decision-rail">
        <section class="cockpit-panel decision-panel">
          <div class="panel-heading"><div><h2>路网状态</h2><p>距离与行驶时间矩阵</p></div></div>
          <dl>
            <div><dt>当前来源</dt><dd class="good">{{ routingLabel }}</dd></div>
            <div><dt>回退机制</dt><dd>{{ routingStatus?.fallback_enabled ? '已启用' : '未启用' }}</dd></div>
            <div><dt>矩阵缓存</dt><dd>{{ routingStatus?.cache_entries ?? 0 }}/{{ routingStatus?.cache_capacity ?? 0 }}</dd></div>
          </dl>
          <p v-if="result.routing.fallback_used" class="matrix-warning"><AlertTriangle :size="13" />OSRM 暂不可用，已安全回退</p>
          <p v-else class="matrix-ok"><CircleCheckBig :size="13" />矩阵服务运行正常</p>
        </section>

        <section class="cockpit-panel decision-panel">
          <div class="panel-heading"><div><h2>运力建议</h2><p>按 82% 目标装载率</p></div></div>
          <dl>
            <div><dt>建议车辆</dt><dd class="large">{{ forecast.recommended_vehicles }} 辆</dd></div>
            <div><dt>冷链需求</dt><dd>{{ forecast.cold_chain_tons.toFixed(1) }} 吨</dd></div>
            <div><dt>现有场景</dt><dd>{{ totalWeight.toFixed(1) }} 吨</dd></div>
          </dl>
        </section>

        <section class="cockpit-panel risk-panel">
          <div class="panel-heading"><div><h2>风险预警</h2><p>未来 {{ forecast.horizon_days }} 日</p></div></div>
          <div class="risk-item"><span :class="forecast.risk_level"><AlertTriangle :size="15" /></span><p><strong>{{ riskCopy }}</strong><small>峰值 {{ forecast.peak_forecast_tons.toFixed(1) }} 吨 · {{ dateLabel(forecast.peak_date) }}</small></p></div>
          <div class="risk-item"><span class="low"><Snowflake :size="15" /></span><p><strong>冷链运力锁定</strong><small>优先保障黄花菜鲜品订单</small></p></div>
          <div class="forecast-provenance">
            <b>{{ forecast.model_family }}</b>
            <span v-if="forecast.validation_mae_tons != null">验证 MAE {{ forecast.validation_mae_tons.toFixed(2) }} 吨</span>
            <span v-else>{{ forecast.fallback_reason || '等待积累更多真实历史数据' }}</span>
          </div>
        </section>

        <section v-if="referenceSummary" class="cockpit-panel reference-panel">
          <div class="panel-heading">
            <div><h2>县域研究基线</h2><p>AHP-GIS · {{ referenceSummary.service_circle_minutes }} 分钟服务圈</p></div>
            <span :class="{ fallback: referenceSummary.coordinate_quality.status !== 'verified' }">{{ referenceQualityLabel }}</span>
          </div>
          <div class="reference-grid">
            <div><span>样本需求</span><b>{{ referenceSummary.reference_demand_tons.toFixed(0) }} 吨</b></div>
            <div><span>县级设施</span><b>{{ referenceSummary.county_facility_count }}</b></div>
            <div><span>乡镇站</span><b>{{ referenceSummary.town_logistics_stations }}</b></div>
            <div><span>村级站</span><b>{{ referenceSummary.village_service_stations }}</b></div>
          </div>
          <div class="reference-load-note">
            <span>今日演示载荷</span>
            <b>{{ (referenceSummary.demo_order_weight_kg / 1000).toFixed(1) }} 吨 · {{ referenceSummary.demo_order_count }} 单</b>
            <em>共配协同 {{ referenceSummary.co_delivery_stations }} 点 · 村级覆盖 {{ referenceSummary.village_coverage_percent.toFixed(1) }}%</em>
          </div>
          <p class="reference-candidates">候选站点 {{ referenceSummary.candidates.length }} 个 · 田间冷库 {{ referenceSummary.field_cold_stores }} 座 · 公路 {{ referenceSummary.road_total_km.toFixed(1) }} km · 优先节点：{{ referenceCandidates.map(item => item.town_name).join(' · ') }}</p>
        </section>

        <button class="dispatch-button" data-guide="dispatch-entry" :disabled="busy" @click="emit('dispatch')">
          <Truck :size="18" />{{ busy ? '正在生成方案' : '生成今日调度' }}<ArrowRight :size="17" />
        </button>
      </aside>
    </div>

    <div class="bottom-rail">
      <div><span class="metric-icon green"><TrendingUp :size="22" /></span><p><small>预测峰值</small><strong>{{ forecast.peak_forecast_tons.toFixed(1) }} 吨</strong><em>{{ dateLabel(forecast.peak_date) }}</em></p></div>
      <div><span class="metric-icon blue"><Snowflake :size="22" /></span><p><small>冷链需求</small><strong>{{ forecast.cold_chain_tons.toFixed(1) }} 吨</strong><em>优先保障鲜品</em></p></div>
      <div><span class="metric-icon green"><Route :size="22" /></span><p><small>预计里程</small><strong>{{ result.metrics.distance_km }} km</strong><em>较基线下降</em></p></div>
      <div><span class="metric-icon amber"><Sparkles :size="22" /></span><p><small>节约成本</small><strong>¥ {{ saving.toLocaleString() }}</strong><em>本次优化估算</em></p></div>
    </div>
  </div>
</template>

<style scoped>
.cockpit{display:flex;flex-direction:column;gap:11px;min-width:0}.metric-rail,.bottom-rail{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));background:#fff;border:1px solid #e1e7e2;border-radius:11px;box-shadow:0 5px 18px rgba(29,68,45,.05)}.metric-rail>div,.bottom-rail>div{display:flex;align-items:center;gap:12px;padding:14px 18px;border-right:1px solid #e8ece9;min-width:0}.metric-rail>div:last-child,.bottom-rail>div:last-child{border:0}.metric-icon{width:39px;height:39px;display:grid;place-items:center;border-radius:50%;flex:0 0 auto}.metric-icon.green{color:#17834f;background:#e8f5ee}.metric-icon.amber{color:#ed8b21;background:#fff3e5}.metric-icon.blue{color:#2878d0;background:#eaf2fd}.metric-rail p,.bottom-rail p{margin:0;display:flex;flex-direction:column;min-width:0}.metric-rail small,.bottom-rail small{font-size:11px;color:#748178}.metric-rail strong{font-size:25px;line-height:1.1;color:#126d41;margin-top:5px}.metric-rail strong i{font-size:11px;font-style:normal;margin-left:3px}.metric-rail .amber-copy{color:#e47c12;font-size:19px}.cockpit-main{display:grid;grid-template-columns:280px minmax(490px,1fr) 265px;gap:11px;height:525px;min-height:0;min-width:0}.analytics-rail,.decision-rail{display:flex;flex-direction:column;gap:11px;min-width:0;min-height:0}.decision-rail{gap:8px}.cockpit-panel{background:#fff;border:1px solid #e1e7e2;border-radius:11px;box-shadow:0 5px 18px rgba(29,68,45,.05);overflow:hidden;min-width:0}.panel-heading{display:flex;align-items:flex-start;justify-content:space-between;padding:13px 14px 8px}.panel-heading h2{font-size:14px;margin:0;color:#1a2b21}.panel-heading p{font-size:9px;margin:4px 0 0;color:#859188}.panel-heading>span{font-size:10px;padding:5px 8px;color:#fff;background:#17834f;border-radius:6px}.forecast-panel{height:273px}.forecast-chart{height:218px}.ranking-panel{flex:1}.ranking-chart{height:194px}.map-panel{position:relative;display:flex;flex-direction:column;min-height:0;height:525px}.map-heading{position:absolute;z-index:3;left:8px;right:8px;top:7px;background:rgba(255,255,255,.92);border-radius:8px;box-shadow:0 3px 12px rgba(20,60,37,.08)}.map-heading .live-state{display:flex;align-items:center;gap:5px;background:#edf7f1;color:#17834f}.live-state i{width:6px;height:6px;background:#20a75d;border-radius:50%}.map-panel :deep(.map-host){height:100%;min-height:0}.map-source{position:absolute;z-index:3;left:14px;bottom:14px;display:flex;align-items:center;gap:7px;padding:8px 10px;background:rgba(255,255,255,.94);border:1px solid #dce5df;border-radius:7px;font-size:9px;color:#526158}.map-source b{color:#17834f}.decision-panel{padding-bottom:5px;flex:0 1 auto}.decision-panel .panel-heading{padding:9px 12px 5px}.decision-panel dl{margin:0 12px}.decision-panel dl>div{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid #edf0ee;font-size:10px}.decision-panel dt{color:#69786f}.decision-panel dd{margin:0;font-weight:700}.decision-panel dd.good{color:#17834f}.decision-panel dd.large{font-size:16px;color:#126d41}.matrix-warning,.matrix-ok{display:flex;align-items:center;gap:5px;margin:6px 12px 2px;font-size:9px}.matrix-warning{color:#dd6d28}.matrix-ok{color:#17834f}.risk-panel{padding-bottom:4px}.risk-item{display:flex;align-items:center;gap:8px;margin:0 12px;padding:5px 0;border-top:1px solid #edf0ee}.risk-item>span{width:26px;height:26px;display:grid;place-items:center;border-radius:7px}.risk-item>span.low{color:#17834f;background:#e9f5ee}.risk-item>span.medium{color:#e47d13;background:#fff2e4}.risk-item>span.high{color:#d84a42;background:#fdeceb}.risk-item p{margin:0}.risk-item strong,.risk-item small{display:block}.risk-item strong{font-size:10px}.risk-item small{font-size:8px;color:#829087;margin-top:2px}.dispatch-button{margin-top:auto;flex:0 0 42px;width:100%;height:42px;border:0;border-radius:9px;background:#0d8b4b;color:#fff;font-weight:750;display:flex;align-items:center;justify-content:center;gap:9px;cursor:pointer;box-shadow:0 8px 18px rgba(13,139,75,.18)}.dispatch-button svg:last-child{margin-left:auto;margin-right:15px}.dispatch-button svg:first-child{margin-left:15px}.dispatch-button:disabled{opacity:.65}.bottom-rail>div{padding:12px 18px}.bottom-rail strong{font-size:18px;color:#163c29;margin-top:3px}.bottom-rail em{font-size:9px;color:#87938b;font-style:normal;margin-top:2px}
.panel-heading>span.fallback{background:#b77621}.forecast-provenance{margin:3px 12px 5px;padding:6px 8px;border-radius:7px;background:#f6f8f6;display:flex;flex-direction:column;gap:2px}.forecast-provenance b{font-size:9px;color:#375346}.forecast-provenance span{font-size:8px;color:#7a877f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.reference-panel{padding-bottom:8px}.reference-panel .panel-heading{padding-bottom:6px}.reference-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin:0 12px}.reference-grid>div{padding:5px 6px;border:1px solid #e5eee8;border-radius:6px;background:#f7faf8}.reference-grid span,.reference-grid b{display:block}.reference-grid span{font-size:8px;color:#849087}.reference-grid b{font-size:12px;color:#1b6f46;margin-top:3px}.reference-load-note{display:grid;grid-template-columns:auto 1fr;align-items:baseline;gap:2px 6px;margin:7px 12px 0;padding:6px 7px;border-radius:6px;background:#f3f8f4;color:#68786e;font-size:8px}.reference-load-note b{font-size:10px;color:#1b6f46}.reference-load-note em{grid-column:1/-1;font-style:normal;color:#8a978f;margin-top:2px}.reference-candidates{margin:7px 12px 0;font-size:8px;line-height:1.45;color:#68786e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cockpit{gap:14px}.metric-rail,.bottom-rail{border-color:#dce5df;box-shadow:0 8px 24px rgba(22,55,38,.035)}.metric-rail>div{padding:17px 20px}.metric-rail small,.bottom-rail small{font-size:11px}.metric-rail strong{font-size:27px;letter-spacing:-.4px}.cockpit-main{grid-template-columns:285px minmax(500px,1fr) 270px;gap:14px;height:560px}.analytics-rail,.decision-rail{gap:12px}.cockpit-panel{border-color:#dce5df;box-shadow:0 8px 24px rgba(22,55,38,.035)}.panel-heading{padding:15px 16px 9px}.panel-heading h2{font-size:15px;letter-spacing:-.15px}.panel-heading p{font-size:10px}.panel-heading>span{font-size:9px;background:#176f47}.forecast-panel{height:292px}.forecast-chart{height:235px}.ranking-chart{height:205px}.map-panel{height:560px}.map-heading{left:10px;right:10px;top:9px;padding:13px 15px;background:rgba(255,255,255,.96);border:1px solid rgba(220,229,223,.8);box-shadow:0 5px 18px rgba(20,60,37,.06)}.map-source{left:16px;bottom:16px;padding:9px 11px;font-size:9px}.decision-panel .panel-heading{padding:11px 13px 6px}.decision-panel dl{margin:0 13px}.decision-panel dl>div{padding:6px 0;font-size:10px}.risk-item{padding:6px 0}.forecast-provenance{margin:4px 12px 6px;padding:7px 9px}.dispatch-button{height:44px;flex-basis:44px;border-radius:9px;box-shadow:0 8px 18px rgba(13,139,75,.14)}.bottom-rail>div{padding:14px 20px}.bottom-rail strong{font-size:19px}
@media(max-width:1250px){.cockpit-main{grid-template-columns:255px minmax(450px,1fr) 245px}.metric-rail>div,.bottom-rail>div{padding-left:12px;padding-right:12px}}
@media(max-width:1100px){.cockpit-main{grid-template-columns:minmax(0,1fr);height:auto}.analytics-rail{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.forecast-panel,.ranking-panel{height:270px}.forecast-chart,.ranking-chart{height:215px}.map-panel{height:520px}.decision-rail{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}.dispatch-button{grid-column:1/-1}}
@media(max-width:760px){.metric-rail,.bottom-rail{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-rail>div,.bottom-rail>div{padding:12px 10px;border-bottom:1px solid #e8ece9}.metric-rail>div:nth-child(2n),.bottom-rail>div:nth-child(2n){border-right:0}.metric-rail strong{font-size:21px}.metric-rail .amber-copy{font-size:16px}.metric-icon{width:34px;height:34px}.analytics-rail,.decision-rail{grid-template-columns:minmax(0,1fr)}.map-panel{height:500px}.bottom-rail strong{font-size:16px}.panel-heading{padding-left:11px;padding-right:11px}}
</style>
