<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Activity, CheckCircle2, RefreshCw, Thermometer, TriangleAlert } from '@lucide/vue'
import {
  acknowledgeTemperatureAlert,
  getColdChainOverview,
  getTemperatureAlerts,
  getTemperatureReadings,
  getTemperatureSensors,
  simulateTemperatureStream,
} from '../services/api'
import type {
  TemperatureAlertView,
  TemperatureOverview,
  TemperatureSensorView,
} from '../types/logistics'
import { LineChart as EChartsLine, } from 'echarts/charts'
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([EChartsLine, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, CanvasRenderer])

const busy = ref(false)
const simulating = ref(false)
const error = ref('')
const message = ref('')
const sensors = ref<TemperatureSensorView[]>([])
const alerts = ref<TemperatureAlertView[]>([])
const overview = ref<TemperatureOverview>()
const selectedSensorId = ref('')
const simulateHours = ref(6)
const statusFilter = ref<'open' | 'acknowledged' | ''>('open')

const chartElement = ref<HTMLElement>()
let chart: echarts.ECharts | undefined

const levelLabels: Record<string, string> = {
  info: '提示',
  warning: '警告',
  critical: '严重',
}
const alertTypeLabels: Record<string, string> = {
  threshold_breach: '阈值越限',
  anomaly_trend: '趋势异常',
}
const statusLabels: Record<string, string> = {
  open: '未处理',
  acknowledged: '已确认',
  resolved: '已解除',
}
const contextLabels: Record<string, string> = {
  outbound: '出库',
  in_transit: '在途',
  inbound: '入库',
  storage: '库内',
}

const selectedSensor = () => sensors.value.find(item => item.id === selectedSensorId.value)
const openAlertCount = () => alerts.value.filter(item => item.status === 'open').length

async function loadSensors(keepSelection = true) {
  const sensorList = await getTemperatureSensors()
  sensors.value = sensorList.items
  if (!keepSelection || !sensors.value.some(item => item.id === selectedSensorId.value)) {
    const preferred = sensors.value.find(item => item.sensor_type === 'vehicle') ?? sensors.value[0]
    selectedSensorId.value = preferred?.id ?? ''
  }
}

async function renderChart() {
  if (!selectedSensorId.value || !chartElement.value) return
  const readings = await getTemperatureReadings(selectedSensorId.value, 120)
  const sensor = selectedSensor()
  const labels = readings.items.map(item => new Date(item.recorded_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
  const values = readings.items.map(item => item.temperature_c)
  const seriesData = readings.items.map(item => ({
    value: item.temperature_c,
    context: contextLabels[item.context] ?? item.context,
  }))
  chart ??= echarts.init(chartElement.value)
  chart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        formatter: (params: Array<{ dataIndex: number; value: number }>) => {
          const point = seriesData[params[0]?.dataIndex]
          return `${labels[params[0]?.dataIndex]} · ${point?.context ?? ''}<br/>温度：${params[0]?.value}℃`
        },
      },
      grid: { left: 44, right: 18, top: 30, bottom: 28 },
      xAxis: { type: 'category', data: labels, boundaryGap: false },
      yAxis: { type: 'value', scale: true, name: '℃' },
      series: [
        {
          name: '温度',
          type: 'line',
          data: values,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { width: 2.5, color: '#178052' },
          itemStyle: { color: '#178052' },
          areaStyle: { color: 'rgba(23,128,82,0.08)' },
          markLine: sensor
            ? {
                silent: true,
                symbol: 'none',
                data: [
                  { yAxis: sensor.target_high_c, lineStyle: { color: '#c9563c', type: 'dashed' }, label: { formatter: `上限 ${sensor.target_high_c}℃`, position: 'insideEndTop' } },
                  { yAxis: sensor.target_low_c, lineStyle: { color: '#3e5368', type: 'dashed' }, label: { formatter: `下限 ${sensor.target_low_c}℃`, position: 'insideEndBottom' } },
                ],
              }
            : undefined,
        },
      ],
    },
    true,
  )
}

async function refreshAll() {
  busy.value = true
  error.value = ''
  try {
    await Promise.all([loadSensors(), loadAlerts()])
    overview.value = await getColdChainOverview()
    await nextTick(renderChart)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '温控监测数据加载失败'
  } finally {
    busy.value = false
  }
}

async function loadAlerts() {
  const alertList = await getTemperatureAlerts(statusFilter.value || undefined, 60)
  alerts.value = alertList.items
}

async function selectSensor(sensorId: string) {
  selectedSensorId.value = sensorId
  error.value = ''
  try {
    await nextTick(renderChart)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '温度曲线加载失败'
  }
}

async function runSimulation() {
  simulating.value = true
  message.value = ''
  error.value = ''
  try {
    const result = await simulateTemperatureStream(simulateHours.value)
    message.value = `已生成 ${result.window_hours} 小时演示温度数据：新增 ${result.readings_created} 条读数、${result.alerts_created} 条预警。`
    await refreshAll()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '演示数据生成失败'
  } finally {
    simulating.value = false
  }
}

async function acknowledge(alertId: number) {
  try {
    await acknowledgeTemperatureAlert(alertId)
    await loadAlerts()
    overview.value = await getColdChainOverview()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '预警确认失败'
  }
}

function resizeChart() {
  chart?.resize()
}

onMounted(async () => {
  window.addEventListener('resize', resizeChart)
  await refreshAll()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
  chart = undefined
})
</script>

<template>
  <div class="temp-monitor">
    <header class="page-heading">
      <div>
        <h1>全程温控监测预警</h1>
        <p>出库 · 在途 · 入库 · 库内存储 · 阈值与趋势双通道预警</p>
      </div>
      <div class="heading-actions">
        <select v-model.number="simulateHours" class="hours-select">
          <option :value="3">近 3 小时</option>
          <option :value="6">近 6 小时</option>
          <option :value="12">近 12 小时</option>
          <option :value="24">近 24 小时</option>
        </select>
        <button class="ghost-button" :disabled="simulating" @click="runSimulation">
          <Activity :size="16" />{{ simulating ? '生成中' : '生成演示温度数据' }}
        </button>
        <button class="ghost-button" :disabled="busy" @click="refreshAll">
          <RefreshCw :size="16" />{{ busy ? '刷新中' : '刷新' }}
        </button>
      </div>
    </header>

    <div class="boundary-note">
      <TriangleAlert :size="15" />
      <span>
        演示边界：温度读数由受控模拟过程生成，用于展示预警链路，不代表真实车载或库内传感数据；
        预警只作为调度参考，冷链任务约束仍由确定性求解器校验。
      </span>
    </div>

    <div v-if="error" class="state-message error">{{ error }}</div>
    <div v-else-if="message" class="state-message ok"><CheckCircle2 :size="14" />{{ message }}</div>

    <section class="metric-strip">
      <div><span>温控采集点</span><strong>{{ overview?.active_sensors ?? 0 }} / {{ overview?.sensor_total ?? 0 }}</strong><small>启用 / 总数</small></div>
      <div><span>累计读数</span><strong>{{ overview?.reading_total ?? 0 }}</strong><small>全程四环节采集</small></div>
      <div><span>未处理预警</span><strong :class="{ danger: openAlertCount() > 0 }">{{ overview?.open_alerts ?? 0 }}</strong><small>含趋势异常提醒</small></div>
      <div><span>严重预警</span><strong :class="{ danger: (overview?.critical_alerts ?? 0) > 0 }">{{ overview?.critical_alerts ?? 0 }}</strong><small>偏差超过阈值一半</small></div>
    </section>

    <div class="main-grid">
      <section class="panel chart-panel">
        <div class="panel-title">
          <div>
            <h2>温度曲线 · {{ selectedSensor()?.name ?? '未选择采集点' }}</h2>
            <p>
              目标区间 {{ selectedSensor()?.target_low_c ?? '--' }} ~ {{ selectedSensor()?.target_high_c ?? '--' }}℃
              · 虚线为越限阈值
            </p>
          </div>
          <Thermometer :size="20" />
        </div>
        <div class="sensor-chips">
          <button
            v-for="sensor in sensors"
            :key="sensor.id"
            class="sensor-chip"
            :class="{ active: sensor.id === selectedSensorId }"
            @click="selectSensor(sensor.id)"
          >
            <span>{{ sensor.sensor_type === 'vehicle' ? '车载' : '库内' }}</span>
            <b>{{ sensor.vehicle_plate ?? sensor.cold_store_name ?? sensor.name }}</b>
            <em v-if="sensor.latest_temperature_c !== null">{{ sensor.latest_temperature_c.toFixed(1) }}℃</em>
          </button>
        </div>
        <div ref="chartElement" class="temp-chart" />
      </section>

      <section class="panel alerts-panel">
        <div class="panel-title">
          <div><h2>预警处置</h2><p>阈值越限与趋势异常双通道</p></div>
          <TriangleAlert :size="20" />
        </div>
        <div class="filter-row">
          <button
            v-for="option in ['open', 'acknowledged', ''] as const"
            :key="option"
            class="filter-chip"
            :class="{ active: statusFilter === option }"
            @click="statusFilter = option; loadAlerts()"
          >
            {{ option === '' ? '全部' : statusLabels[option] }}
          </button>
        </div>
        <p v-if="!alerts.length" class="empty-state">当前筛选下没有预警记录。</p>
        <div v-else class="alert-list">
          <article v-for="alert in alerts" :key="alert.id" class="alert-item" :class="alert.level">
            <div class="alert-head">
              <span class="badge level">{{ levelLabels[alert.level] }}</span>
              <span class="badge type">{{ alertTypeLabels[alert.alert_type] }}</span>
              <span class="badge status">{{ statusLabels[alert.status] }}</span>
              <small>{{ new Date(alert.created_at).toLocaleString('zh-CN') }}</small>
            </div>
            <p class="alert-message">{{ alert.message }}</p>
            <div class="alert-foot">
              <small>{{ alert.sensor_id }}</small>
              <button v-if="alert.status === 'open'" class="ack-button" @click="acknowledge(alert.id)">确认处置</button>
              <small v-else-if="alert.acknowledged_by">处置人：{{ alert.acknowledged_by }}</small>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.temp-monitor {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}
.page-heading h1 {
  margin: 0;
  font-size: 22px;
}
.page-heading p {
  margin: 4px 0 0;
  color: #5d6f66;
  font-size: 13px;
}
.heading-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.hours-select {
  border: 1px solid #c9d8cf;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  background: #fff;
}
.ghost-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #c9d8cf;
  background: #fff;
  color: #30473b;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}
.ghost-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.boundary-note {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  background: #fff5dd;
  border-left: 4px solid #b97915;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12.5px;
  color: #6b5a31;
}
.state-message {
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
}
.state-message.error {
  background: #fdecec;
  color: #a13333;
}
.state-message.ok {
  background: #e5f4ec;
  color: #178052;
  display: flex;
  align-items: center;
  gap: 6px;
}
.metric-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.metric-strip > div {
  background: #fff;
  border: 1px solid #dde8e1;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.metric-strip span {
  font-size: 12px;
  color: #66776e;
}
.metric-strip strong {
  font-size: 22px;
  color: #0d5b3d;
}
.metric-strip strong.danger {
  color: #c9563c;
}
.metric-strip small {
  font-size: 11.5px;
  color: #8b9791;
}
.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 1fr);
  gap: 16px;
  align-items: start;
}
.panel {
  background: #fff;
  border: 1px solid #dde8e1;
  border-radius: 12px;
  padding: 16px;
}
.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  color: #178052;
}
.panel-title h2 {
  margin: 0;
  font-size: 15px;
  color: #30473b;
}
.panel-title p {
  margin: 3px 0 0;
  font-size: 12px;
  color: #66776e;
}
.sensor-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.sensor-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #c9d8cf;
  background: #f7faf8;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #51625a;
}
.sensor-chip.active {
  border-color: #178052;
  background: #eaf4ee;
  color: #0d5b3d;
}
.sensor-chip span {
  font-size: 10.5px;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 0 5px;
}
.sensor-chip b {
  font-weight: 600;
}
.sensor-chip em {
  font-style: normal;
  color: #178052;
}
.temp-chart {
  width: 100%;
  height: 320px;
}
.filter-row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.filter-chip {
  border: 1px solid #c9d8cf;
  background: #fff;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #51625a;
}
.filter-chip.active {
  background: #0d5b3d;
  border-color: #0d5b3d;
  color: #fff;
}
.empty-state {
  color: #8b9791;
  font-size: 12.5px;
  margin: 6px 0;
}
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow: auto;
}
.alert-item {
  border: 1px solid #e3ece7;
  border-radius: 10px;
  padding: 10px 12px;
}
.alert-item.critical {
  border-left: 4px solid #c9563c;
}
.alert-item.warning {
  border-left: 4px solid #f3b63e;
}
.alert-item.info {
  border-left: 4px solid #6f8f80;
}
.alert-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.alert-head small {
  color: #8b9791;
  font-size: 11px;
  margin-left: auto;
}
.badge {
  font-size: 11px;
  border-radius: 999px;
  padding: 2px 8px;
  background: #f1f6f3;
  color: #51625a;
}
.badge.level {
  background: #fdecec;
  color: #a13333;
}
.alert-item.info .badge.level {
  background: #eef3f8;
  color: #3e5368;
}
.alert-item.warning .badge.level {
  background: #fff5dd;
  color: #b97915;
}
.alert-message {
  margin: 8px 0;
  font-size: 12.5px;
  color: #30473b;
  line-height: 1.5;
}
.alert-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.alert-foot small {
  color: #8b9791;
  font-size: 11px;
}
.ack-button {
  border: none;
  background: #0d5b3d;
  color: #fff;
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
}
@media (max-width: 1100px) {
  .main-grid,
  .metric-strip {
    grid-template-columns: 1fr;
  }
}
</style>
