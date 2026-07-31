<script setup lang="ts">
import {
  CheckCircle2, Clock3, FileDown, Fingerprint,
  FlaskConical, KeyRound, Play, Route, Settings2, ShieldCheck, TrendingDown,
} from '@lucide/vue'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  downloadExperimentReport, getExperiments, getSessionRole, hasSession,
  login, runAlgorithmExperiment,
} from '../services/api'
import type { ExperimentView } from '../types/logistics'

const emit = defineEmits<{ sessionChange: [role: string] }>()
const authorized = ref(hasSession() && ['admin', 'dispatcher'].includes(getSessionRole()))
const experiments = ref<ExperimentView[]>([])
const selected = ref<ExperimentView>()
const busy = ref(false)
const error = ref('')
const message = ref('')
const chartElement = ref<HTMLDivElement>()
const loginForm = reactive({ username: 'admin', password: '' })
echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

let chart: ECharts | undefined

const summary = computed(() => selected.value?.summary)
const shortFingerprint = computed(() => {
  const value = selected.value?.scenario_fingerprint ?? ''
  return value ? `${value.slice(0, 18)}…${value.slice(-10)}` : '—'
})

function renderChart() {
  if (!chartElement.value || !selected.value) return
  chart ??= echarts.init(chartElement.value)
  const results = selected.value.results
  const reductions = results.map(item => item.distance_reduction_pct)
  const reductionMin = Math.min(0, Math.floor(Math.min(...reductions, 0) - 1))
  const reductionMax = Math.max(5, Math.ceil(Math.max(...reductions, 0) + 1))
  chart.setOption({
    animationDuration: 500,
    color: ['#dfe3e1', '#07643b', '#f28a16'],
    grid: { left: 58, right: 58, top: 66, bottom: 42 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: {
      top: 10, left: 2, itemWidth: 14, itemHeight: 9,
      textStyle: { color: '#596860', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: results.map(item => item.case_name),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#dce3de' } },
      axisLabel: { color: '#526159', fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value', name: '里程（km）',
        nameTextStyle: { color: '#78857d', fontSize: 10 },
        axisLabel: { color: '#859088', fontSize: 9 },
        splitLine: { lineStyle: { color: '#edf1ee', type: 'dashed' } },
      },
      {
        type: 'value', name: '改善率（%）', min: reductionMin, max: reductionMax,
        nameTextStyle: { color: '#78857d', fontSize: 10 },
        axisLabel: { color: '#859088', fontSize: 9, formatter: '{value}%' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '业务基线', type: 'bar', barWidth: 34,
        data: results.map(item => item.baseline_distance_km),
        itemStyle: { color: '#dfe3e1' },
        label: { show: true, position: 'top', color: '#526159', fontSize: 9 },
      },
      {
        name: 'OR-Tools 推荐', type: 'bar', barWidth: 34,
        data: results.map(item => item.optimized_distance_km),
        itemStyle: { color: '#07643b' },
        label: { show: true, position: 'top', color: '#174630', fontSize: 9 },
      },
      {
        name: '里程改善', type: 'line', yAxisIndex: 1, smooth: true, symbolSize: 7,
        data: results.map(item => item.distance_reduction_pct),
        lineStyle: { color: '#f28a16', width: 2 },
        itemStyle: { color: '#f28a16' },
        label: {
          show: true, position: 'top', color: '#df7107', fontSize: 9,
          formatter: ({ value }: { value: number }) => `${value}%`,
        },
      },
    ],
  }, true)
}

async function loadExperiments() {
  if (!authorized.value) return
  busy.value = true
  error.value = ''
  try {
    experiments.value = (await getExperiments()).items
    selected.value ??= experiments.value[0]
    await nextTick(renderChart)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '实验记录加载失败'
  } finally {
    busy.value = false
  }
}

async function authenticate() {
  busy.value = true
  error.value = ''
  try {
    const session = await login(loginForm.username, loginForm.password)
    if (!['admin', 'dispatcher'].includes(session.role)) {
      throw new Error('当前账号没有算法实验权限')
    }
    authorized.value = true
    loginForm.password = ''
    emit('sessionChange', session.role)
    await loadExperiments()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '登录失败'
    busy.value = false
  }
}

async function runExperiment() {
  busy.value = true
  error.value = ''
  message.value = '正在依次求解标准负荷、旺季峰值和冷链压力案例…'
  try {
    const created = await runAlgorithmExperiment()
    experiments.value = [created, ...experiments.value.filter(item => item.id !== created.id)]
    selected.value = created
    message.value = `${created.experiment_code} 已完成，实验口径和结果已持久化。`
    await nextTick(renderChart)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '算法实验运行失败'
    message.value = ''
  } finally {
    busy.value = false
  }
}

async function exportReport() {
  if (!selected.value) return
  busy.value = true
  error.value = ''
  try {
    const blob = await downloadExperimentReport(selected.value.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `算法实验-${selected.value.experiment_code}.html`
    link.click()
    URL.revokeObjectURL(url)
    message.value = '实验报告已生成，可在浏览器中打印为 PDF。'
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '实验报告导出失败'
  } finally {
    busy.value = false
  }
}

async function chooseExperiment(item: ExperimentView) {
  selected.value = item
  await nextTick(renderChart)
}

function resizeChart() {
  chart?.resize()
}

onMounted(() => {
  window.addEventListener('resize', resizeChart)
  loadExperiments()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
})
</script>

<template>
  <article v-if="!authorized" class="lab-login">
    <div class="login-mark"><FlaskConical :size="28" /></div>
    <h2>进入算法对照实验室</h2>
    <p>实验会调用 OR-Tools 运行三组压力案例，仅管理员和调度员可以创建。</p>
    <form @submit.prevent="authenticate">
      <label><span>账号</span><input v-model.trim="loginForm.username" autocomplete="username" required /></label>
      <label><span>密码</span><input v-model="loginForm.password" type="password" autocomplete="current-password" required /></label>
      <button class="lab-primary" :disabled="busy"><KeyRound :size="16" />{{ busy ? '正在验证' : '安全登录' }}</button>
    </form>
    <div v-if="error" class="lab-error">{{ error }}</div>
  </article>

  <div v-else class="algorithm-lab">
    <header class="lab-heading">
      <div>
        <h1>算法对照实验室</h1>
        <p>同一场景、同一约束、同一口径 · 可重复验证优化收益</p>
      </div>
      <div class="lab-actions">
        <button class="lab-primary" :disabled="busy" @click="runExperiment"><Play :size="16" />{{ busy ? '实验运行中' : '运行新实验' }}</button>
        <button class="lab-secondary" :disabled="busy || !selected" @click="exportReport"><FileDown :size="16" />导出实验报告</button>
      </div>
    </header>

    <div v-if="error" class="lab-error">{{ error }}</div>
    <div v-else-if="message" class="lab-message"><CheckCircle2 :size="14" />{{ message }}</div>

    <section v-if="selected" class="metric-strip">
      <div><span>平均里程降低</span><strong>{{ summary?.average_distance_reduction_pct.toFixed(1) ?? '0.0' }}% <TrendingDown :size="19" /></strong><small>相对业务基线</small></div>
      <div><span>累计成本差额</span><strong>¥ {{ summary?.total_cost_saving_cny.toLocaleString() ?? 0 }}</strong><small>正值节省 · 负值增加</small></div>
      <div><span>订单服务率</span><strong>{{ summary?.average_service_rate.toFixed(1) ?? '0.0' }}%</strong><small>OR-Tools 推荐平均</small></div>
      <div><span>实验编号</span><strong class="experiment-code">{{ selected.experiment_code }}</strong><small><CheckCircle2 :size="13" />{{ selected.status === 'completed' ? '已完成' : selected.status }}</small></div>
    </section>

    <div v-if="selected" class="lab-main">
      <section class="lab-panel chart-panel">
        <div class="panel-title"><div><h2>基线与 OR-Tools 对照</h2><p>确定性业务轮询基线 vs. 约束优化推荐</p></div><Route :size="20" /></div>
        <div ref="chartElement" class="comparison-chart" />
      </section>
      <aside class="lab-panel config-panel">
        <div class="panel-title"><div><h2>实验配置</h2><p>复跑时保持下列口径一致</p></div><Settings2 :size="19" /></div>
        <dl>
          <div><dt>场景版本</dt><dd>{{ selected.scenario_key }}</dd></div>
          <div><dt>求解器</dt><dd>OR-Tools Routing</dd></div>
          <div><dt>单案例时限</dt><dd>{{ selected.time_limit_seconds }} 秒</dd></div>
          <div class="fingerprint"><dt>场景指纹</dt><dd><Fingerprint :size="14" />{{ shortFingerprint }}</dd></div>
          <div><dt>业务基线</dt><dd>约束校验轮询启发式</dd></div>
        </dl>
        <div class="repro-note"><ShieldCheck :size="17" /><p><b>可重复证据</b><span>输入指纹、压力规则、求解时限和输出指标已同时入库。</span></p></div>
      </aside>
    </div>

    <div v-if="selected" class="lab-bottom">
      <section class="lab-panel result-panel">
        <div class="panel-title"><div><h2>压力案例结果</h2><p>三类需求压力下的同口径比较</p></div><Clock3 :size="18" /></div>
        <div class="result-table">
          <div class="result-row result-head"><span>案例</span><span>状态</span><span>基线里程</span><span>推荐里程</span><span>成本差额</span><span>车辆</span><span>未分配</span></div>
          <div v-for="item in selected.results" :key="item.case_key" class="result-row">
            <strong>{{ item.case_name }}<small>{{ item.demand_tons.toFixed(2) }} 吨</small></strong>
            <span class="case-status"><i />{{ item.status === 'infeasible' ? '不可行' : '已完成' }}</span>
            <span>{{ item.baseline_distance_km.toFixed(1) }} km</span>
            <b>{{ item.optimized_distance_km.toFixed(1) }} km</b>
            <em>¥ {{ item.cost_saving_cny.toLocaleString() }}</em>
            <span>{{ item.vehicles_used }} 辆</span>
            <span>{{ item.unassigned_orders }} 单</span>
          </div>
        </div>
      </section>
      <aside class="lab-panel history-panel">
        <div class="panel-title"><div><h2>实验历史</h2><p>最近 {{ experiments.length }} 次</p></div><FlaskConical :size="18" /></div>
        <button v-for="item in experiments.slice(0, 6)" :key="item.id" :class="{ selected: item.id === selected.id }" @click="chooseExperiment(item)">
          <i /><span><b>{{ item.experiment_code }}</b><small>{{ new Date(item.completed_at ?? item.created_at).toLocaleString('zh-CN') }}</small></span><strong>›</strong>
        </button>
        <p v-if="!experiments.length" class="empty-history">运行首个实验后将在此留痕。</p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.algorithm-lab{display:flex;flex-direction:column;gap:12px;color:#183b29}.lab-heading{display:flex;align-items:flex-start;justify-content:space-between;padding:1px 2px 10px}.lab-heading h1{margin:0;font-size:28px;letter-spacing:.5px;color:#0a4930}.lab-heading p{margin:8px 0 0;font-size:12px;color:#707d75}.lab-actions{display:flex;gap:10px}.lab-primary,.lab-secondary{height:40px;display:flex;align-items:center;justify-content:center;gap:8px;border-radius:6px;padding:0 17px;font-weight:700;font-size:12px;cursor:pointer}.lab-primary{border:1px solid #075c39;background:#075c39;color:#fff;box-shadow:0 4px 12px rgba(7,92,57,.13)}.lab-secondary{border:1px solid #ced7d1;background:#fff;color:#34483d}.lab-primary:disabled,.lab-secondary:disabled{opacity:.55;cursor:not-allowed}.lab-error,.lab-message{display:flex;align-items:center;gap:7px;padding:9px 12px;border-radius:6px;font-size:11px}.lab-error{color:#ad3f39;background:#fff0ef;border:1px solid #f0d0cd}.lab-message{color:#126b42;background:#ecf6f0;border:1px solid #d4eadc}.metric-strip{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #e1e6e3;border-bottom:1px solid #e1e6e3;background:#fff}.metric-strip>div{padding:11px 18px;border-right:1px solid #e2e7e4}.metric-strip>div:last-child{border:0}.metric-strip span,.metric-strip small,.metric-strip strong{display:flex;align-items:center}.metric-strip span{font-size:11px;color:#69766f}.metric-strip strong{gap:6px;margin-top:7px;font-size:25px;color:#07643b;line-height:1}.metric-strip small{gap:5px;margin-top:7px;font-size:9px;color:#808a84}.metric-strip .experiment-code{font-size:18px;letter-spacing:.6px}.lab-main{display:grid;grid-template-columns:minmax(610px,1fr) 305px;gap:12px;min-height:326px}.lab-panel{background:#fff;border:1px solid #dfe5e1;border-radius:7px;overflow:hidden}.panel-title{display:flex;align-items:center;justify-content:space-between;padding:13px 15px;border-bottom:1px solid #e8ece9}.panel-title h2{margin:0;font-size:14px;color:#173b29}.panel-title p{margin:4px 0 0;font-size:9px;color:#849088}.panel-title>svg{color:#687b70}.comparison-chart{height:267px}.config-panel dl{margin:0}.config-panel dl>div{display:flex;justify-content:space-between;gap:15px;padding:12px 15px;border-bottom:1px solid #e7ece8;font-size:10px}.config-panel dt{color:#5f6d65}.config-panel dd{margin:0;text-align:right;font-weight:650;color:#3d4c44;word-break:break-all}.config-panel .fingerprint{display:block}.config-panel .fingerprint dd{display:flex;align-items:center;justify-content:flex-end;gap:5px;margin-top:6px;font-family:Consolas,monospace;font-size:9px;color:#547061}.repro-note{display:flex;gap:9px;margin:11px 13px;padding:10px;background:#eff7f2;color:#157149}.repro-note p{margin:0}.repro-note b,.repro-note span{display:block;font-size:9px}.repro-note span{margin-top:3px;color:#63766a;line-height:1.5}.lab-bottom{display:grid;grid-template-columns:minmax(650px,1fr) 305px;gap:12px}.result-table{font-size:10px}.result-row{display:grid;grid-template-columns:1.15fr .8fr 1fr 1fr 1fr .65fr .65fr;align-items:center;min-height:44px;padding:0 14px;border-bottom:1px solid #e9edea;color:#5c6961}.result-row:last-child{border:0}.result-row strong small{display:block;margin-top:3px;color:#8a948e;font-size:8px;font-weight:400}.result-row b{color:#07643b}.result-row em{font-style:normal;color:#e47509;font-weight:700}.result-head{min-height:34px;background:#f7f9f7;color:#748179;font-weight:700}.case-status{display:flex;align-items:center;gap:5px;color:#26744e}.case-status i,.history-panel button>i{width:6px;height:6px;border-radius:50%;background:#138453}.history-panel button{width:100%;display:grid;grid-template-columns:7px 1fr 12px;align-items:center;gap:8px;padding:9px 13px;border:0;border-bottom:1px solid #e9edea;background:#fff;text-align:left;cursor:pointer}.history-panel button:hover,.history-panel button.selected{background:#edf7f1}.history-panel button span b,.history-panel button span small{display:block}.history-panel button span b{font-size:9px;color:#284637}.history-panel button span small{margin-top:3px;font-size:8px;color:#87918b}.history-panel button>strong{color:#24724c}.empty-history{padding:20px;color:#849088;font-size:10px}.lab-login{width:420px;margin:70px auto;padding:28px;background:#fff;border:1px solid #dfe7e1;border-radius:11px;box-shadow:0 12px 30px rgba(18,72,44,.08)}.login-mark{width:50px;height:50px;display:grid;place-items:center;border-radius:12px;background:#e9f5ed;color:#127345}.lab-login h2{margin:16px 0 6px;font-size:20px;color:#173b29}.lab-login>p{font-size:10px;line-height:1.7;color:#7b8780}.lab-login form{display:flex;flex-direction:column;gap:12px;margin-top:17px}.lab-login label span{display:block;margin-bottom:6px;font-size:10px;font-weight:700;color:#4b5c52}.lab-login input{width:100%;height:39px;border:1px solid #dce4de;border-radius:7px;padding:0 10px;outline:none}.lab-login input:focus{border-color:#28845a;box-shadow:0 0 0 3px #e6f4eb}.lab-login .lab-primary{width:100%;margin-top:3px}@media(max-width:1250px){.lab-main,.lab-bottom{grid-template-columns:minmax(580px,1fr) 275px}.metric-strip>div{padding-left:12px;padding-right:12px}}
</style>
