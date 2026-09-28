<script setup lang="ts">
import {
  Activity, AlertTriangle, Boxes, BrainCircuit, ChevronRight, CircleCheckBig, CircleHelp, Clock3,
  CloudSun, Database, Download, FileSpreadsheet, Gauge, KeyRound, LayoutDashboard,
  FlaskConical, LockKeyhole, LogOut, MapPinned, Menu, Play, RefreshCw, Route, Satellite,
  ChartNoAxesCombined, ServerCog, Settings2, ShieldCheck, Sparkles, Truck, UploadCloud, Warehouse,
} from '@lucide/vue'
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MetricCompare from './components/MetricCompare.vue'
import OperationGuide from './components/OperationGuide.vue'
import {
  activateScenario, clearAdminSession, downloadScenarioTemplate, explainRun,
  getAIConfig, getCurrentWeather, getDemandForecast, getLatestRun, getRoutingStatus, getRunHistory, getScenario,
  getQidongReferenceSummary, getScenarioSpatialStatus,
  getScenarioVersions, getSessionRole, getSessionUser, hasSession, logout,
  login, optimizeScenario, reoptimizeScenario, saveAIConfig, testAIConfig,
  uploadScenario,
} from './services/api'
import type {
  AIConfigView, AIExplanationResponse, CurrentWeather, DemandForecast, OptimizeResult, RoutingStatus,
  QidongReferenceSummary, RunSummary, Scenario, ScenarioSpatialStatus, ScenarioVersionView,
} from './types/logistics'

const MasterDataCenter = defineAsyncComponent(() => import('./components/MasterDataCenter.vue'))
const ScenarioGovernance = defineAsyncComponent(() => import('./components/ScenarioGovernance.vue'))
const OperationalReadinessCenter = defineAsyncComponent(() => import('./components/OperationalReadinessCenter.vue'))
const ProfessionalCountyMap = defineAsyncComponent(() => import('./components/ProfessionalCountyMap.vue'))
const AlgorithmLab = defineAsyncComponent(() => import('./components/AlgorithmLab.vue'))
const DecisionCockpit = defineAsyncComponent(() => import('./components/DecisionCockpit.vue'))
const ExecutionCenter = defineAsyncComponent(() => import('./components/ExecutionCenter.vue'))
const SystemSettings = defineAsyncComponent(() => import('./components/SystemSettings.vue'))
const OrderRequestCenter = defineAsyncComponent(() => import('./components/OrderRequestCenter.vue'))
const ColdChainStorage = defineAsyncComponent(() => import('./components/ColdChainStorage.vue'))
const TemperatureMonitor = defineAsyncComponent(() => import('./components/TemperatureMonitor.vue'))

const route = useRoute()
const router = useRouter()
const demoResetRequested = route.query.demo_reset === '1'
if (demoResetRequested) {
  sessionStorage.removeItem('qizhi_event_resolved')
  localStorage.removeItem('qizhi_operation_guide_v1')
  clearAdminSession()
}
let snapshotTimer: number | undefined
let weatherTimer: number | undefined
let snapshotSyncing = false
type PlatformView = 'overview' | 'dispatch' | 'events' | 'execution' | 'experiments' | 'history' | 'masterData' | 'scenarios' | 'readiness' | 'settings' | 'orderRequests' | 'coldChain' | 'coldMonitor'
type GuidedStep = {
  eyebrow: string
  title: string
  description: string
  tip: string
  target: string
  actionLabel: string
  route: PlatformView
}
const GUIDE_COMPLETION_KEY = 'qizhi_operation_guide_v1'
const guideSteps: GuidedStep[] = [
  {
    eyebrow: '快速上手',
    title: '先从运营总览掌握全局',
    description: '这里汇总今日需求、建议运力、路网状态和风险预警。每天进入系统后，先确认数据与引擎状态是否正常。',
    tip: '下一步将定位右侧的“生成今日调度”入口。',
    target: '[data-guide="overview-nav"]',
    actionLabel: '查看生成入口',
    route: 'overview',
  },
  {
    eyebrow: '第一个业务动作',
    title: '从这里生成当天调度方案',
    description: '系统会根据订单、车辆、容量、冷链和时间窗约束生成可执行路线。正式操作时，请点击被高亮的“生成今日调度”。',
    tip: '本引导不会触发求解；继续后只带你进入智能调度页面。',
    target: '[data-guide="dispatch-entry"]',
    actionLabel: '进入智能调度',
    route: 'overview',
  },
  {
    eyebrow: '查看与调整方案',
    title: '在智能调度页检查路线',
    description: '地图展示车辆路线与配送顺序，右侧显示评分、装载率和车辆任务。数据变化后，可使用顶部按钮重新生成候选方案。',
    tip: '先检查地图、车辆数和未分配订单，再决定是否重新生成。',
    target: '[data-guide="dispatch-action"]',
    actionLabel: '查看异常处置',
    route: 'dispatch',
  },
  {
    eyebrow: '动态响应',
    title: '车辆故障从这里启动处置',
    description: '动态事件页面会冻结已完成任务，只对剩余订单重新求解。确认故障位置和受影响车辆后，再点击“启动处置”。',
    tip: '处置完成后应检查延误、冷链约束和替代车辆是否合理。',
    target: '[data-guide="event-action"]',
    actionLabel: '查看执行闭环',
    route: 'events',
  },
  {
    eyebrow: '执行闭环',
    title: '最后完成审批、下发与反馈',
    description: '执行中心用于提交方案、管理员审批、下发驾驶员，以及驾驶员接单、发车和完成配送。每一步都会留下操作记录。',
    tip: '实际使用顺序：提交方案 → 审核通过 → 下发驾驶员 → 驾驶员确认执行。',
    target: '[data-guide="execution-workspace"]',
    actionLabel: '完成引导',
    route: 'execution',
  },
]
const routeView = () => (route.name === 'settings' ? 'settings' : String(route.name || 'overview')) as PlatformView
const scenario = ref<Scenario>()
const result = ref<OptimizeResult>()
const loading = ref(true)
const error = ref('')
const activeView = ref<PlatformView>(routeView())
const selectedRoute = ref(0)
const eventResolved = ref(sessionStorage.getItem('qizhi_event_resolved') === 'true')
const eventProgress = ref(eventResolved.value ? 100 : 0)
const eventVehicleLabel = ref('在途车辆')
const runHistory = ref<RunSummary[]>([])
const authenticated = ref(hasSession())
const sessionRole = ref(getSessionRole())
const sessionUser = ref(getSessionUser())
const authBusy = ref(false)
const aiBusy = ref(false)
const aiTesting = ref(false)
const aiConfig = ref<AIConfigView>()
const settingsMessage = ref('')
const settingsMessageKind = ref<'success' | 'error' | 'info'>('info')
const scenarioVersions = ref<ScenarioVersionView[]>([])
const scenarioBusy = ref(false)
const selectedScenarioFile = ref<File>()
const scenarioMessage = ref('')
const scenarioMessageKind = ref<'success' | 'error' | 'info'>('info')
const aiExplanation = ref<AIExplanationResponse>()
const explanationBusyRun = ref('')
const forecast = ref<DemandForecast>()
const routingStatus = ref<RoutingStatus>()
const referenceSummary = ref<QidongReferenceSummary>()
const spatialStatus = ref<ScenarioSpatialStatus>()
const weather = ref<CurrentWeather>()
const weatherLoading = ref(true)
const guideOpen = ref(false)
const guideIndex = ref(0)
const loginForm = reactive({ username: '', password: '' })
const aiForm = reactive({
  provider: 'openai-compatible',
  base_url: 'https://api.openai.com/v1',
  model_name: '',
  api_key: '',
  enabled: true,
  temperature: 0.2,
})
const providerHints: Record<string, string> = {
  openai: '官方地址：https://api.openai.com/v1',
  deepseek: '官方地址：https://api.deepseek.com；推荐模型：deepseek-v4-flash',
  qwen: '默认使用阿里云百炼北京地域兼容地址；API Key 必须与地域及计费方案匹配',
  'openai-compatible': '请按服务商文档填写兼容接口地址和模型 ID',
  custom: '请按服务商文档填写兼容接口地址和模型 ID',
}
const providerHint = computed(() => providerHints[aiForm.provider] ?? providerHints.custom)
const weatherDisplay = computed(() => {
  if (weather.value) return `祁东 ${weather.value.temperature_c.toFixed(1)}℃`
  return weatherLoading.value ? '祁东 · 天气加载中' : '祁东 · 天气暂不可用'
})
const weatherTooltip = computed(() => {
  if (!weather.value) return '正在获取祁东县实时天气'
  const stale = weather.value.stale ? ' · 使用最近一次数据' : ''
  return `${weather.value.weather_label} · 体感 ${weather.value.apparent_temperature_c.toFixed(1)}℃ · 湿度 ${weather.value.humidity_percent}% · 风速 ${weather.value.wind_speed_kmh} km/h${stale}`
})

const activeRoute = computed(() => result.value?.routes[selectedRoute.value] ?? result.value?.routes[0])
const activeRouteLoadRate = computed(() => {
  const routeItem = activeRoute.value
  if (!routeItem || !scenario.value) return 0
  const capacity = scenario.value.vehicles.find((vehicle) => vehicle.id === routeItem.vehicle_id)?.capacity_kg
  return capacity ? Math.round(routeItem.load_kg / capacity * 100) : 0
})
const improvement = computed(() => {
  if (!result.value) return 0
  return Math.round((1 - result.value.metrics.distance_km / result.value.baseline_metrics.distance_km) * 100)
})
const decisionScore = computed(() => result.value?.decision_score?.total ?? 0)
const decisionGrade = computed(() => result.value?.decision_score?.grade ?? '待评估')
const orchestrationLabel = computed(() => {
  const orchestration = result.value?.ai_orchestration
  if (!orchestration?.used) return '确定性多目标优化'
  return `${orchestration.provider ?? 'AI'} · ${orchestration.model_name ?? '已配置模型'}`
})
const activeEventCount = computed(() => eventResolved.value ? 0 : 1)
const decisionExplanationItems = computed(() => {
  const items = result.value?.explanations ?? []
  return items
    .map((text) => {
      if (text.includes('已从可用运力中移除')) {
        return { kind: 'mechanism', title: '故障隔离', text }
      }
      if (text.startsWith('事件位置')) {
        return { kind: 'data', title: '位置确认', text }
      }
      if (text.includes('冻结')) {
        return { kind: 'mechanism', title: '约束重建', text }
      }
      if (text.includes('接替受影响订单') || text.includes('重新校验')) {
        return { kind: 'result', title: '结果校验', text }
      }
      if (text.startsWith('AI 风险提示：')) {
        return { kind: 'risk', title: '风险提示', text: text.replace('AI 风险提示：', '') }
      }
      if (text.startsWith('AI 在') || text.startsWith('透明评分选择')) {
        return { kind: 'decision', title: '方案选择', text }
      }
      if (text.startsWith('采用“')) {
        return { kind: 'strategy', title: '求解策略', text }
      }
      if (/本次使用\d+辆车/.test(text)) {
        return { kind: 'result', title: '执行结果', text }
      }
      if (text.includes('OSRM') || text.includes('路网距离')) {
        return { kind: 'routing', title: '路网依据', text }
      }
      if (text.includes('空间坐标快照')) {
        return { kind: 'data', title: '数据版本', text }
      }
      return { kind: 'info', title: '补充说明', text }
    })
    .slice(0, 7)
})
const pageTitle = computed(() => ({
  overview: '县域物流智能决策驾驶舱',
  dispatch: '县域物流智能调度中心',
  events: '动态事件与实时重调度',
  execution: '调度审批与执行中心',
  experiments: '算法评估中心',
  history: '调度方案数据中心',
  masterData: '物流基础数据中心',
  scenarios: '县域业务场景管理',
  readiness: '运营评估中心',
  settings: '系统设置与服务配置',
  orderRequests: '用户订单申请中心',
  coldChain: '冷链仓储共享调度',
  coldMonitor: '全程温控监测预警',
}[activeView.value]))
const crumbTitle = computed(() => ({
  overview: '运营总览',
  dispatch: '智能协同调度',
  events: '动态事件处置',
  execution: '业务执行闭环',
  experiments: '算法评估',
  history: '历史方案',
  masterData: '基础数据中心',
  scenarios: '场景与数据导入',
  readiness: '运营能力评估',
  settings: '系统设置',
  orderRequests: '订单申请',
  coldChain: '冷链仓储共享',
  coldMonitor: '全程温控监测',
}[activeView.value]))
const pageDescription = computed(() =>
  activeView.value === 'overview'
    ? '祁东县黄花菜城乡双向配送 · 路网、运力与需求一屏统筹'
    : `${scenario.value?.name ?? ''} · ${scenario.value?.orders.length ?? 0} 个订单 · ${scenario.value?.vehicles.length ?? 0} 台可用车辆`,
)

function go(view: PlatformView) {
  const paths: Record<PlatformView, string> = {
    overview: '/overview',
    dispatch: '/dispatch',
    events: '/events',
    execution: '/execution',
    experiments: '/experiments',
    history: '/history',
    masterData: '/master-data/orders',
    scenarios: '/scenarios',
    readiness: '/readiness',
    settings: '/settings/ai',
    orderRequests: '/order-requests',
    coldChain: '/cold-chain',
    coldMonitor: '/cold-monitor',
  }
  return router.push(paths[view])
}

async function showGuideStep(index: number) {
  const nextIndex = Math.max(0, Math.min(index, guideSteps.length - 1))
  const step = guideSteps[nextIndex]
  await go(step.route)
  guideIndex.value = nextIndex
}

async function startOperationGuide() {
  await showGuideStep(0)
  guideOpen.value = true
}

async function advanceOperationGuide() {
  if (guideIndex.value >= guideSteps.length - 1) {
    finishOperationGuide()
    return
  }
  await showGuideStep(guideIndex.value + 1)
}

async function previousOperationGuide() {
  await showGuideStep(guideIndex.value - 1)
}

function finishOperationGuide() {
  localStorage.setItem(GUIDE_COMPLETION_KEY, 'completed')
  guideOpen.value = false
}

async function loadDecisionData() {
  const [forecastResult, routingResult] = await Promise.all([
    getDemandForecast(7),
    getRoutingStatus(),
  ])
  forecast.value = forecastResult
  routingStatus.value = routingResult
  try {
    referenceSummary.value = await getQidongReferenceSummary()
  } catch {
    // The reference layer is supplementary; an older backend must not block the cockpit.
    referenceSummary.value = undefined
  }
}

async function refreshWeather() {
  if (!authenticated.value) return
  if (!weather.value) weatherLoading.value = true
  try {
    weather.value = await getCurrentWeather()
  } catch {
    if (!weather.value) weather.value = undefined
  } finally {
    weatherLoading.value = false
  }
}

async function synchronizeOperationalSnapshot(force = false) {
  // 执行中心由自身按角色加载审批/驾驶员任务，不应被全局驾驶舱快照阻塞。
  if (!authenticated.value || activeView.value === 'execution' || snapshotSyncing || loading.value) return
  snapshotSyncing = true
  try {
    const currentScenario = await getScenario()
    const latestResult = await getLatestRun(currentScenario.id)
    const scenarioChanged = scenario.value?.id !== currentScenario.id
    const resultChanged = Boolean(latestResult && latestResult.run_id !== result.value?.run_id)
    if (force || scenarioChanged || resultChanged) {
      scenario.value = currentScenario
      if (latestResult) result.value = latestResult
      await Promise.all([
        loadDecisionData(),
        getScenarioSpatialStatus().then(value => { spatialStatus.value = value }),
      ])
      selectedRoute.value = 0
    }
  } catch {
    // 后台同步失败时保留当前可用快照，下一轮自动重试。
  } finally {
    snapshotSyncing = false
  }
}

function handleWindowFocus() {
  void synchronizeOperationalSnapshot()
}

function handleVisibilityChange() {
  if (document.visibilityState === 'visible') void synchronizeOperationalSnapshot()
}

async function generateTodayDispatch() {
  await router.push('/dispatch')
  await runOptimization()
}

async function runOptimization() {
  loading.value = true
  error.value = ''
  try {
    // 订单申请审核后会激活新的 master-data 场景；求解必须使用当前场景，
    // 否则驾驶员看到的是旧快照，且新场景没有最近运行记录时会触发无权限求解。
    result.value = await optimizeScenario('bidirectional-v2', scenario.value?.id)
    selectedRoute.value = 0
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '优化失败'
  } finally {
    loading.value = false
  }
}

async function runReoptimization() {
  await router.push('/events')
  eventResolved.value = false
  sessionStorage.removeItem('qizhi_event_resolved')
  loading.value = true
  eventProgress.value = 20
  try {
    eventProgress.value = 62
    eventVehicleLabel.value = '湘D·A1234'
    result.value = await reoptimizeScenario()
    eventProgress.value = 100
    eventResolved.value = true
    sessionStorage.setItem('qizhi_event_resolved', 'true')
  } catch (cause) {
    eventResolved.value = false
    error.value = cause instanceof Error ? cause.message : '重调度失败'
  } finally {
    loading.value = false
  }
}

async function showHistory() {
  await router.push('/history')
  loading.value = true
  error.value = ''
  try {
    runHistory.value = (await getRunHistory()).items
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '历史记录加载失败'
  } finally {
    loading.value = false
  }
}

async function explainHistoryRun(runId: string) {
  if (!authenticated.value) {
    error.value = '请先在系统设置中使用管理员账号登录，再调用 AI 方案解读。'
    return
  }
  explanationBusyRun.value = runId
  error.value = ''
  try {
    aiExplanation.value = await explainRun(runId)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'AI 方案解读失败'
  } finally {
    explanationBusyRun.value = ''
  }
}

async function loadScenarioVersions(clearMessage = true) {
  if (!authenticated.value) return
  scenarioBusy.value = true
  if (clearMessage) scenarioMessage.value = ''
  try {
    scenarioVersions.value = (await getScenarioVersions()).items
  } catch (cause) {
    scenarioMessageKind.value = 'error'
    scenarioMessage.value = cause instanceof Error ? cause.message : '场景版本加载失败'
  } finally {
    scenarioBusy.value = false
  }
}

async function showScenarios() {
  await router.push('/scenarios')
  await loadScenarioVersions()
}

function chooseScenarioFile(event: Event) {
  const input = event.target as HTMLInputElement
  selectedScenarioFile.value = input.files?.[0]
  scenarioMessage.value = selectedScenarioFile.value
    ? `已选择：${selectedScenarioFile.value.name}`
    : ''
  scenarioMessageKind.value = 'info'
}

async function importScenarioFile() {
  if (!selectedScenarioFile.value) {
    scenarioMessageKind.value = 'error'
    scenarioMessage.value = '请先选择 .xlsx 场景文件'
    return
  }
  scenarioBusy.value = true
  try {
    const response = await uploadScenario(selectedScenarioFile.value)
    scenarioMessageKind.value = 'success'
    scenarioMessage.value = `导入成功：${response.scenario.version_key}，校验通过后已保存为草稿版本。`
    selectedScenarioFile.value = undefined
    await loadScenarioVersions(false)
  } catch (cause) {
    scenarioMessageKind.value = 'error'
    scenarioMessage.value = cause instanceof Error ? cause.message : '场景导入失败'
  } finally {
    scenarioBusy.value = false
  }
}

async function activateScenarioVersion(item: ScenarioVersionView) {
  scenarioBusy.value = true
  scenarioMessage.value = ''
  try {
    const activated = await activateScenario(item.id)
    scenario.value = await getScenario()
    spatialStatus.value = await getScenarioSpatialStatus()
    scenarioMessageKind.value = 'success'
    scenarioMessage.value = `已激活 ${activated.version_key}，后续求解将使用该场景。`
    await loadScenarioVersions(false)
  } catch (cause) {
    scenarioMessageKind.value = 'error'
    scenarioMessage.value = cause instanceof Error ? cause.message : '场景激活失败'
  } finally {
    scenarioBusy.value = false
  }
}

async function handleScenarioActivated() {
  scenario.value = await getScenario()
  spatialStatus.value = await getScenarioSpatialStatus()
}

async function saveScenarioTemplate() {
  scenarioBusy.value = true
  try {
    const blob = await downloadScenarioTemplate()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '祁智运场景导入模板.xlsx'
    link.click()
    URL.revokeObjectURL(url)
    scenarioMessageKind.value = 'success'
    scenarioMessage.value = '模板下载已开始'
  } catch (cause) {
    scenarioMessageKind.value = 'error'
    scenarioMessage.value = cause instanceof Error ? cause.message : '模板下载失败'
  } finally {
    scenarioBusy.value = false
  }
}

function applyAIConfig(config: AIConfigView | null) {
  aiConfig.value = config ?? undefined
  if (!config) return
  aiForm.provider = config.provider
  aiForm.base_url = config.base_url
  aiForm.model_name = config.model_name
  aiForm.api_key = ''
  aiForm.enabled = config.enabled
  aiForm.temperature = config.temperature
}

function applyProviderPreset() {
  const presets: Record<string, { base_url: string; model_name: string }> = {
    openai: { base_url: 'https://api.openai.com/v1', model_name: '' },
    deepseek: { base_url: 'https://api.deepseek.com', model_name: 'deepseek-v4-flash' },
    qwen: {
      base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      model_name: 'qwen-plus',
    },
  }
  const preset = presets[aiForm.provider]
  if (!preset) return
  aiForm.base_url = preset.base_url
  aiForm.model_name = preset.model_name
  settingsMessageKind.value = 'info'
  settingsMessage.value = '已按服务商自动填写推荐接口地址，请确认 API Key 来自同一平台。'
}

async function loadAIConfig(clearMessage = true) {
  if (!authenticated.value) return
  aiBusy.value = true
  if (clearMessage) settingsMessage.value = ''
  try {
    applyAIConfig(await getAIConfig())
  } catch (cause) {
    settingsMessageKind.value = 'error'
    settingsMessage.value = cause instanceof Error ? cause.message : 'AI 配置加载失败'
    if (settingsMessage.value.includes('登录') || settingsMessage.value.includes('凭证')) {
      clearAdminSession()
      authenticated.value = false
    }
  } finally {
    aiBusy.value = false
  }
}

async function showSettings() {
  await router.push('/settings/ai')
}

async function adminLogin() {
  authBusy.value = true
  settingsMessage.value = ''
  try {
    const response = await login(loginForm.username, loginForm.password)
    if (response.role !== 'admin') throw new Error('当前账号没有系统配置权限')
    authenticated.value = true
    loginForm.password = ''
    settingsMessageKind.value = 'success'
    settingsMessage.value = '管理员身份验证成功'
    if (activeView.value === 'scenarios') {
      scenarioMessageKind.value = 'success'
      scenarioMessage.value = '管理员身份验证成功'
      await loadScenarioVersions(false)
    } else {
      await loadAIConfig(false)
    }
  } catch (cause) {
    clearAdminSession()
    authenticated.value = false
    settingsMessageKind.value = 'error'
    settingsMessage.value = cause instanceof Error ? cause.message : '登录失败'
  } finally {
    authBusy.value = false
  }
}

function adminLogout() {
  clearAdminSession()
  authenticated.value = false
  aiConfig.value = undefined
  scenarioVersions.value = []
  settingsMessageKind.value = 'info'
  settingsMessage.value = '已安全退出管理员会话'
}

async function persistAIConfig() {
  aiBusy.value = true
  settingsMessage.value = ''
  try {
    const payload = {
      name: aiConfig.value?.name ?? '默认 AI 服务',
      description: aiConfig.value?.description,
      provider: aiForm.provider,
      base_url: aiForm.base_url,
      model_name: aiForm.model_name,
      enabled: aiForm.enabled,
      temperature: Number(aiForm.temperature),
      ...(aiForm.api_key.trim() ? { api_key: aiForm.api_key.trim() } : {}),
    }
    applyAIConfig(await saveAIConfig(payload))
    settingsMessageKind.value = 'success'
    settingsMessage.value = 'AI 配置已加密保存'
  } catch (cause) {
    settingsMessageKind.value = 'error'
    settingsMessage.value = cause instanceof Error ? cause.message : 'AI 配置保存失败'
  } finally {
    aiBusy.value = false
  }
}

async function checkAIConnection() {
  aiTesting.value = true
  settingsMessage.value = ''
  try {
    const response = await testAIConfig()
    settingsMessageKind.value = response.success ? 'success' : 'error'
    settingsMessage.value = `${response.message}（${response.latency_ms} ms）`
    await loadAIConfig(false)
  } catch (cause) {
    settingsMessageKind.value = 'error'
    settingsMessage.value = cause instanceof Error ? cause.message : 'AI 连接测试失败'
  } finally {
    aiTesting.value = false
  }
}

async function initializePlatform() {
  loading.value = true
  error.value = ''
  // 执行中心有独立的任务接口和权限模型。驾驶员/调度员直接进入该页面时，
  // 不需要先加载驾驶舱的预测、路网快照或求解结果。
  if (activeView.value === 'execution') {
    loading.value = false
    return
  }
  try {
    scenario.value = await getScenario()
    const latestResult = await getLatestRun(scenario.value.id)
    await Promise.all([
      loadDecisionData(),
      getScenarioSpatialStatus().then(value => { spatialStatus.value = value }),
    ])
    if (latestResult) {
      result.value = latestResult
    } else {
      if (sessionRole.value === 'admin' || sessionRole.value === 'dispatcher') {
        await runOptimization()
      }
    }
    loading.value = false
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '平台初始化失败'
    loading.value = false
  }
}

async function signOut() {
  await logout()
  authenticated.value = false
  sessionRole.value = ''
  sessionUser.value = ''
  scenario.value = undefined
  result.value = undefined
  referenceSummary.value = undefined
  weather.value = undefined
  activeView.value = 'overview'
  await router.replace('/login')
}

onMounted(async () => {
  window.addEventListener('qizhi-session-expired', async () => {
    authenticated.value = false
    scenario.value = undefined
    result.value = undefined
    referenceSummary.value = undefined
    await router.replace('/login')
  })
  if (demoResetRequested) {
    authenticated.value = false
    sessionRole.value = ''
    sessionUser.value = ''
    await router.replace('/login')
  } else if (authenticated.value) {
    void refreshWeather()
    await initializePlatform()
    if ((sessionRole.value === 'admin' || sessionRole.value === 'dispatcher') && localStorage.getItem(GUIDE_COMPLETION_KEY) !== 'completed') {
      await startOperationGuide()
    }
  }
  if (activeView.value === 'history') await showHistory()
  if (activeView.value === 'scenarios') await loadScenarioVersions()
  window.addEventListener('focus', handleWindowFocus)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  snapshotTimer = window.setInterval(() => {
    void synchronizeOperationalSnapshot()
  }, 15000)
  weatherTimer = window.setInterval(() => {
    void refreshWeather()
  }, 600000)
})

onBeforeUnmount(() => {
  window.removeEventListener('focus', handleWindowFocus)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  if (snapshotTimer !== undefined) window.clearInterval(snapshotTimer)
  if (weatherTimer !== undefined) window.clearInterval(weatherTimer)
})

watch(() => route.name, () => {
  activeView.value = routeView()
  if (activeView.value === 'execution') {
    loading.value = false
    return
  }
  if (!scenario.value || !result.value) {
    void initializePlatform()
    return
  }
  void synchronizeOperationalSnapshot()
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><Route :size="25" /></div>
        <div><strong>祁智运</strong><span>AI LOGISTICS</span></div>
      </div>
      <nav>
        <button class="nav-item" data-guide="overview-nav" :class="{ active: activeView === 'overview' }" @click="go('overview')"><LayoutDashboard :size="18" /><span>运营总览</span></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher'" class="nav-item" :class="{ active: activeView === 'dispatch' }" @click="go('dispatch')"><MapPinned :size="18" /><span>智能调度</span></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher'" class="nav-item" :class="{ active: activeView === 'events' }" @click="go('events')"><Activity :size="18" /><span>动态事件</span><i v-if="activeEventCount">{{ activeEventCount }}</i></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher' || sessionRole === 'driver'" class="nav-item" data-guide="execution-nav" :class="{ active: activeView === 'execution' }" @click="go('execution')"><Truck :size="18" /><span>执行中心</span></button>
        <button v-if="sessionRole === 'admin'" class="nav-item" :class="{ active: activeView === 'orderRequests' }" @click="go('orderRequests')"><FileSpreadsheet :size="18" /><span>订单申请</span></button>
        <button v-if="sessionRole === 'admin'" class="nav-item" :class="{ active: activeView === 'scenarios' }" @click="showScenarios"><Warehouse :size="18" /><span>场景管理</span></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher'" class="nav-item" :class="{ active: activeView === 'coldChain' }" @click="go('coldChain')"><Snowflake :size="18" /><span>冷链仓储</span></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher'" class="nav-item" :class="{ active: activeView === 'coldMonitor' }" @click="go('coldMonitor')"><Thermometer :size="18" /><span>温控监测</span></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher'" class="nav-item" :class="{ active: activeView === 'experiments' }" @click="go('experiments')"><FlaskConical :size="18" /><span>算法评估</span></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher'" class="nav-item" :class="{ active: activeView === 'masterData' }" @click="go('masterData')"><Boxes :size="18" /><span>基础数据</span></button>
        <button class="nav-item" :class="{ active: activeView === 'history' }" @click="showHistory"><Database :size="18" /><span>方案历史</span></button>
        <button v-if="sessionRole === 'admin' || sessionRole === 'dispatcher'" class="nav-item" :class="{ active: activeView === 'readiness' }" @click="go('readiness')"><ChartNoAxesCombined :size="18" /><span>运营评估</span></button>
      </nav>
      <div class="side-bottom">
        <button v-if="sessionRole === 'admin'" class="nav-item" :class="{ active: activeView === 'settings' }" @click="showSettings"><Settings2 :size="18" /><span>系统设置</span></button>
        <div class="operator"><div>{{ sessionUser.slice(0, 1) }}</div><p><strong>{{ sessionUser || '平台用户' }}</strong><span>{{ sessionRole === 'admin' ? '系统管理员' : sessionRole === 'driver' ? '配送驾驶员' : '运营调度员' }}</span></p></div>
      </div>
    </aside>

    <main>
      <header class="topbar">
        <div class="crumb"><Menu :size="18" /><span>运营中心</span><ChevronRight :size="14" /><b>{{ crumbTitle }}</b></div>
        <div class="top-status">
          <span class="weather-status" :title="weatherTooltip"><CloudSun :size="16" />{{ weatherDisplay }}<small v-if="weather">{{ weather.weather_label }}</small></span>
          <span class="online"><i />引擎在线</span>
          <button class="top-guide" type="button" @click="startOperationGuide"><CircleHelp :size="16" /><span>操作引导</span></button>
          <button class="top-user" type="button" @click="signOut"><span>{{ sessionUser || '当前用户' }}</span><LogOut :size="15" />退出</button>
        </div>
      </header>

      <section v-if="scenario && result" class="content">
        <div v-if="activeView !== 'experiments' && activeView !== 'settings' && activeView !== 'masterData' && activeView !== 'readiness'" class="page-heading">
          <div>
            <p v-if="activeView !== 'overview'" class="eyebrow"><Sparkles :size="14" /> 县域物流 · 智能协同优化</p>
            <h1>{{ pageTitle }}</h1>
            <p>{{ pageDescription }}</p>
          </div>
          <button v-if="activeView === 'dispatch'" class="primary" data-guide="dispatch-action" :disabled="loading" @click="runOptimization">
            <RefreshCw :class="{ spin: loading }" :size="16" />{{ loading ? '正在生成候选方案' : '重新生成方案' }}
          </button>
          <button v-else-if="activeView === 'events'" class="primary danger" data-guide="event-action" :disabled="loading" @click="runReoptimization">
            <Play :size="16" />{{ loading ? '正在处置' : eventResolved ? '重新计算方案' : '启动处置' }}
          </button>
          <button v-else-if="activeView === 'history'" class="primary" :disabled="loading" @click="showHistory">
            <RefreshCw :class="{ spin: loading }" :size="16" />刷新记录
          </button>
          <button v-else-if="activeView === 'scenarios' && authenticated" class="primary" :disabled="scenarioBusy" @click="saveScenarioTemplate">
            <Download :size="16" />下载 Excel 模板
          </button>
        </div>

        <div v-if="error" class="error"><AlertTriangle :size="17" />{{ error }}</div>

        <template v-if="activeView === 'overview'">
          <DecisionCockpit
            v-if="forecast"
            :scenario="scenario"
            :result="result"
            :forecast="forecast"
            :routing-status="routingStatus"
            :reference-summary="referenceSummary"
            :busy="loading"
            @dispatch="generateTodayDispatch"
          />
          <article v-else class="card cockpit-loading"><BrainCircuit :size="28" /><span>正在汇总路网与需求预测...</span></article>
        </template>

        <template v-else-if="activeView === 'dispatch'">
          <div class="workspace">
            <article class="card map-card">
              <ProfessionalCountyMap
                :scenario="scenario"
                :result="result"
                :spatial-status="spatialStatus"
                :selected-route="selectedRoute"
                @select-route="index => selectedRoute = index"
                @open-settings="router.push('/settings/map')"
              />
            </article>

            <aside class="right-stack">
              <article class="card score">
                <div class="score-top"><span>综合绩效评分</span><b>{{ decisionScore }}<small>/100</small></b></div>
                <div class="score-bar"><i :style="{ width: `${decisionScore}%` }" /></div>
                <div class="score-foot"><span><CircleCheckBig :size="14" />{{ decisionGrade }} · 约束已校验</span><strong>里程降低 {{ improvement }}%</strong></div>
              </article>

              <article class="card control">
                <div class="card-title"><div><h2>调度控制台</h2><p>{{ orchestrationLabel }}</p></div><BrainCircuit :size="22" /></div>
                <div class="control-grid">
                  <div><span>订单量</span><b>{{ scenario.orders.length }}<small>单</small></b></div>
                  <div><span>货量</span><b>{{ (scenario.orders.reduce((s,o)=>s+o.weight_kg,0)/1000).toFixed(1) }}<small>吨</small></b></div>
                  <div><span>冷链订单</span><b>{{ scenario.orders.filter(o=>o.cold_chain).length }}<small>单</small></b></div>
                  <div><span>准时率</span><b>{{ result.metrics.on_time_rate }}<small>%</small></b></div>
                </div>
                <button class="simulate" @click="runReoptimization"><AlertTriangle :size="15" />模拟冷链车故障并重调度</button>
              </article>

              <article class="card routes">
                <div class="card-title"><div><h2>车辆任务</h2><p>{{ result.routes.length }} 条推荐路线</p></div><Gauge :size="20" /></div>
                <button v-for="(routeItem,index) in result.routes" :key="routeItem.vehicle_id" :class="{ selected: selectedRoute===index }" @click="selectedRoute=index">
                  <div class="route-color" :style="{background:['#17834f','#f2a51a','#386fdd','#8a5bd7'][index%4]}" />
                  <div><strong>{{ routeItem.plate }}</strong><span>{{ routeItem.cold_chain ? '冷链运输' : '常温运输' }} · {{ routeItem.stops.length-2 }}站</span></div>
                  <b>{{ routeItem.distance_km }}<small>km</small></b>
                </button>
              </article>
            </aside>
          </div>

          <div class="bottom-grid">
            <article class="card result-card">
              <div class="result-head"><div><h2>优化前后对比</h2><p>同一批订单、同一组约束条件</p></div><span><Sparkles :size="14" />{{ result.ai_orchestration?.used ? 'AI 协同推荐' : '优化引擎推荐' }}</span></div>
              <MetricCompare :baseline="result.baseline_metrics" :optimized="result.metrics" />
            </article>
            <article class="card route-detail" v-if="activeRoute">
              <div><span>当前路线</span><strong>{{ activeRoute.plate }}</strong></div>
              <div><span>装载率</span><strong>{{ activeRouteLoadRate }}%</strong></div>
              <div><span>预计耗时</span><strong>{{ activeRoute.duration_minutes }} min</strong></div>
              <div><span>配送顺序</span><p>{{ activeRoute.stops.slice(1,-1).map(s=>s.node_name).join(' → ') }}</p></div>
            </article>
          </div>
        </template>

        <template v-else-if="activeView === 'events'">
          <div class="event-grid">
            <article class="card map-card event-map">
              <ProfessionalCountyMap
                :scenario="scenario"
                :result="result"
                :spatial-status="spatialStatus"
                :selected-route="selectedRoute"
                :event-mode="!eventResolved"
                @select-route="index => selectedRoute = index"
                @open-settings="router.push('/settings/map')"
              />
            </article>
            <aside class="event-side">
              <article class="event-alert" :class="{ resolved: eventResolved }">
                <CircleCheckBig v-if="eventResolved" :size="22" />
                <AlertTriangle v-else :size="22" />
                <div>
                  <span>{{ eventResolved ? '事件已闭环' : '待处置事件' }}</span>
                  <h2>{{ eventResolved ? `冷链车 ${eventVehicleLabel} 运力已接替` : `冷链车 ${eventVehicleLabel} 发生故障` }}</h2>
                  <p v-if="eventResolved">{{ result.event_location?.location_name || '事件位置' }} · 新路线已生成，故障车辆已移出任务</p>
                  <p v-else>{{ result.event_location?.location_name || '位置待确认' }} · 等待启动约束重建与增量求解</p>
                </div>
              </article>
              <article class="card process">
                <div class="card-title"><div><h2>协同处置进度</h2><p>从感知到下发的完整决策链</p></div><BrainCircuit :size="21" /></div>
                <div class="progress"><i :style="{width:`${eventProgress}%`}" /></div>
                <ol>
                  <li :class="{ done: eventProgress >= 20 }"><CircleCheckBig :size="17" /><div><b>事件识别</b><span>车辆状态、剩余货量与订单位置已锁定</span></div></li>
                  <li :class="{ done: eventProgress >= 45 }"><CircleCheckBig :size="17" /><div><b>约束重建</b><span>冻结已完成节点，保留冷链与时间窗约束</span></div></li>
                  <li :class="{ done: eventProgress >= 70 }"><CircleCheckBig :size="17" /><div><b>增量求解</b><span>候选车辆与受影响订单已重新匹配</span></div></li>
                  <li :class="{ done: eventProgress >= 100 }"><CircleCheckBig :size="17" /><div><b>方案下发</b><span>新路线已生成，等待驾驶员确认</span></div></li>
                </ol>
              </article>
              <article class="card delta">
                <h2>处置结果</h2>
                <div><span>受影响订单</span><b>4 单</b></div>
                <div><span>新增紧急订单</span><b>1 单</b></div>
                <div><span>预计最大延误</span><b class="amber-text">18 分钟</b></div>
                <div><span>冷链约束</span><b class="green-text">100% 满足</b></div>
              </article>
              <article class="card ai-note decision-evidence">
                <div class="decision-evidence-head">
                  <span><Sparkles :size="15" />{{ result.ai_orchestration?.used ? 'AI 协同依据' : '优化决策依据' }}</span>
                  <small>{{ result.ai_orchestration?.used ? '模型参与候选复核' : '确定性规则与求解证据' }}</small>
                </div>
                <div v-if="eventResolved" class="decision-evidence-list">
                  <div v-for="item in decisionExplanationItems" :key="`${item.title}-${item.text}`" :class="item.kind">
                    <i><AlertTriangle v-if="item.kind === 'risk'" :size="13" /><CircleCheckBig v-else :size="13" /></i>
                    <p><b>{{ item.title }}</b><span>{{ item.text }}</span></p>
                  </div>
                </div>
                <p v-else class="decision-empty">完成事件处置后，将在此展示方案选择、约束校验、路网依据和风险提示。</p>
              </article>
            </aside>
          </div>
        </template>

        <template v-else-if="activeView === 'execution'">
          <ExecutionCenter @session-change="role => authenticated = role === 'admin'" />
        </template>

        <template v-else-if="activeView === 'experiments'">
          <AlgorithmLab @session-change="role => authenticated = role === 'admin'" />
        </template>

        <template v-else-if="activeView === 'readiness'">
          <OperationalReadinessCenter />
        </template>

        <template v-else-if="activeView === 'masterData'">
          <MasterDataCenter />
        </template>

        <template v-else-if="activeView === 'orderRequests'">
          <OrderRequestCenter mode="admin" />
        </template>

        <template v-else-if="activeView === 'coldChain'">
          <ColdChainStorage />
        </template>

        <template v-else-if="activeView === 'coldMonitor'">
          <TemperatureMonitor />
        </template>

        <template v-else-if="activeView === 'history'">
          <div class="history-layout">
            <article class="card history-summary">
              <div><Database :size="20" /><span>已持久化方案</span><b>{{ runHistory.length }}</b></div>
              <div><Route :size="20" /><span>最近优化里程</span><b>{{ runHistory[0]?.distance_km ?? 0 }} km</b></div>
              <div><Activity :size="20" /><span>动态事件方案</span><b>{{ runHistory.filter(item => item.event_type).length }}</b></div>
              <div><Clock3 :size="20" /><span>最近求解耗时</span><b>{{ runHistory[0]?.solve_time_ms ?? 0 }} ms</b></div>
            </article>
            <article v-if="aiExplanation" class="card history-ai-result">
              <div class="ai-result-head">
                <div><Sparkles :size="18" /><span>AI 方案解读</span></div>
                <small>{{ aiExplanation.provider }} · {{ aiExplanation.model_name }} · {{ aiExplanation.run_id }}</small>
              </div>
              <p>{{ aiExplanation.explanation }}</p>
            </article>
            <article class="card history-table-card">
              <div class="card-title">
                <div><h2>调度历史记录</h2><p>数据来自 PostgreSQL/本地 SQLite，按创建时间倒序排列</p></div>
                <span class="db-state"><i /> 数据库已连接</span>
              </div>
              <div class="history-table">
                <div class="history-row history-head">
                  <span>方案编号</span><span>类型</span><span>状态</span><span>里程</span><span>成本</span><span>车辆</span><span>求解耗时</span><span>创建时间</span><span>AI</span>
                </div>
                <div v-for="item in runHistory" :key="item.run_id" class="history-row">
                  <strong>{{ item.run_id }}</strong>
                  <span>{{ item.event_type ? '事件重调度' : '常规优化' }}</span>
                  <span><i class="status-dot" />{{ item.status }}</span>
                  <span>{{ item.distance_km }} km</span>
                  <span>¥ {{ item.estimated_cost_cny }}</span>
                  <span>{{ item.vehicles_used }} 辆</span>
                  <span>{{ item.solve_time_ms }} ms</span>
                  <span>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
                  <button class="row-action" :disabled="explanationBusyRun === item.run_id" @click="explainHistoryRun(item.run_id)">
                    <Sparkles :size="12" />{{ explanationBusyRun === item.run_id ? '分析中' : '解读' }}
                  </button>
                </div>
                <div v-if="!runHistory.length" class="history-empty">暂无调度记录，请先执行一次智能优化。</div>
              </div>
            </article>
          </div>
        </template>

        <template v-else-if="activeView === 'scenarios'">
          <ScenarioGovernance @activated="handleScenarioActivated" />
        </template>

        <template v-else-if="false">
          <div class="scenario-layout">
            <article v-if="!authenticated" class="card admin-login">
              <div class="login-icon"><LockKeyhole :size="26" /></div>
              <p class="eyebrow">管理员验证</p>
              <h2>进入场景管理中心</h2>
              <p class="login-copy">场景导入和激活会影响后续调度求解，仅管理员可以操作。</p>
              <form @submit.prevent="adminLogin">
                <label>
                  <span>管理员账号</span>
                  <input v-model.trim="loginForm.username" autocomplete="username" required />
                </label>
                <label>
                  <span>管理员密码</span>
                  <input v-model="loginForm.password" type="password" autocomplete="current-password" required />
                </label>
                <button class="primary login-submit" :disabled="authBusy">
                  <KeyRound :size="16" />{{ authBusy ? '正在验证' : '安全登录' }}
                </button>
              </form>
              <div v-if="scenarioMessage" class="settings-message" :class="scenarioMessageKind">{{ scenarioMessage }}</div>
            </article>

            <template v-else>
              <article class="card import-card">
                <div class="import-icon"><UploadCloud :size="24" /></div>
                <div class="import-copy">
                  <p class="eyebrow">标准化数据接入</p>
                  <h2>导入县域物流场景</h2>
                  <p>上传后先执行字段、引用、时间窗、冷链和运力校验；通过后保存为草稿，不会自动影响当前调度。</p>
                </div>
                <label class="file-picker">
                  <FileSpreadsheet :size="17" />
                  <span>{{ selectedScenarioFile?.name ?? '选择 .xlsx 文件' }}</span>
                  <input type="file" accept=".xlsx" @change="chooseScenarioFile" />
                </label>
                <button class="primary" :disabled="scenarioBusy || !selectedScenarioFile" @click="importScenarioFile">
                  <UploadCloud :size="16" />{{ scenarioBusy ? '正在校验' : '上传并校验' }}
                </button>
              </article>

              <div v-if="scenarioMessage" class="settings-message scenario-message" :class="scenarioMessageKind">{{ scenarioMessage }}</div>

              <article class="card version-card">
                <div class="card-title">
                  <div><h2>场景版本</h2><p>激活版本将用于调度、动态事件和异步求解；历史版本保持不可变。</p></div>
                  <span class="db-state"><i /> {{ scenarioVersions.length }} 个版本</span>
                </div>
                <div class="version-list">
                  <div v-for="item in scenarioVersions" :key="item.id" class="version-row" :class="{ active: item.status === 'active' }">
                    <div class="version-status">
                      <i />
                      <span>{{ item.status === 'active' ? '当前激活' : item.status === 'draft' ? '待激活' : '历史版本' }}</span>
                    </div>
                    <div class="version-name">
                      <strong>{{ item.name }}</strong>
                      <span>{{ item.version_key }} · {{ item.county_name }}</span>
                    </div>
                    <div class="version-count"><b>{{ item.node_count }}</b><span>节点</span></div>
                    <div class="version-count"><b>{{ item.order_count }}</b><span>订单</span></div>
                    <div class="version-count"><b>{{ item.vehicle_count }}</b><span>车辆</span></div>
                    <div class="version-source">
                      <span>{{ item.source_type === 'excel' ? 'Excel 导入' : '系统内置' }}</span>
                      <small>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</small>
                    </div>
                    <button
                      class="secondary activate-button"
                      :disabled="scenarioBusy || item.status === 'active'"
                      @click="activateScenarioVersion(item)"
                    >
                      <CircleCheckBig :size="14" />{{ item.status === 'active' ? '使用中' : '激活' }}
                    </button>
                  </div>
                  <div v-if="!scenarioVersions.length && !scenarioBusy" class="history-empty">暂无场景版本。</div>
                </div>
              </article>
            </template>
          </div>
        </template>

        <template v-else>
          <SystemSettings />
          <div v-if="false" class="settings-layout" aria-hidden="true">
            <article v-if="!authenticated" class="card admin-login">
              <div class="login-icon"><LockKeyhole :size="26" /></div>
              <p class="eyebrow">管理员验证</p>
              <h2>进入 AI 配置中心</h2>
              <p class="login-copy">模型服务涉及密钥与数据安全，仅管理员可查看和修改。登录凭证只保存在当前浏览器会话中。</p>
              <form @submit.prevent="adminLogin">
                <label>
                  <span>管理员账号</span>
                  <input v-model.trim="loginForm.username" autocomplete="username" required />
                </label>
                <label>
                  <span>管理员密码</span>
                  <input v-model="loginForm.password" type="password" autocomplete="current-password" required />
                </label>
                <button class="primary login-submit" :disabled="authBusy">
                  <KeyRound :size="16" />{{ authBusy ? '正在验证' : '安全登录' }}
                </button>
              </form>
              <div v-if="settingsMessage" class="settings-message" :class="settingsMessageKind">{{ settingsMessage }}</div>
            </article>

            <template v-else>
              <div class="settings-main">
                <article class="card ai-config-card">
                  <div class="card-title settings-title">
                    <div>
                      <p class="eyebrow"><ServerCog :size="14" /> OpenAI 兼容接口</p>
                      <h2>大模型服务配置</h2>
                      <p>用于解释调度结果与生成决策建议；路径求解仍由 OR-Tools 确定性完成。</p>
                    </div>
                    <button class="text-button" type="button" @click="adminLogout"><LogOut :size="14" />退出登录</button>
                  </div>

                  <form class="ai-form" @submit.prevent="persistAIConfig">
                    <div class="form-grid">
                      <label>
                        <span>服务类型</span>
                        <select v-model="aiForm.provider" @change="applyProviderPreset">
                          <option value="openai-compatible">OpenAI 兼容服务</option>
                          <option value="openai">OpenAI</option>
                          <option value="deepseek">DeepSeek</option>
                          <option value="qwen">通义千问</option>
                          <option value="custom">其他兼容服务</option>
                        </select>
                        <small>{{ providerHint }}</small>
                      </label>
                      <label>
                        <span>模型标识</span>
                        <input v-model.trim="aiForm.model_name" placeholder="填写服务商提供的模型 ID" required />
                      </label>
                      <label class="span-two">
                        <span>API Base URL</span>
                        <input v-model.trim="aiForm.base_url" type="url" placeholder="https://服务商地址/v1" required />
                      </label>
                      <label class="span-two">
                        <span>API Key</span>
                        <div class="secret-field">
                          <KeyRound :size="15" />
                          <input
                            v-model="aiForm.api_key"
                            type="password"
                            autocomplete="new-password"
                            :placeholder="aiConfig?.has_api_key ? `已配置 ${aiConfig?.api_key_masked}；留空则不修改` : '首次配置必须填写'"
                          />
                        </div>
                        <small>保存后使用 Fernet 对称加密入库，接口和页面不会返回明文。</small>
                      </label>
                      <label>
                        <span>生成温度 <b>{{ Number(aiForm.temperature).toFixed(1) }}</b></span>
                        <input v-model.number="aiForm.temperature" type="range" min="0" max="2" step="0.1" />
                      </label>
                      <label class="switch-row">
                        <span><b>启用 AI 解释</b><small>关闭后保留配置，但不允许调用模型。</small></span>
                        <input v-model="aiForm.enabled" type="checkbox" />
                      </label>
                    </div>
                    <div class="form-actions">
                      <button class="secondary" type="button" :disabled="aiTesting || aiBusy || !aiConfig" @click="checkAIConnection">
                        <Satellite :class="{ spin: aiTesting }" :size="16" />{{ aiTesting ? '正在测试' : '测试连接' }}
                      </button>
                      <button class="primary" :disabled="aiBusy">
                        <ShieldCheck :size="16" />{{ aiBusy ? '正在保存' : '加密保存配置' }}
                      </button>
                    </div>
                  </form>
                  <div v-if="settingsMessage" class="settings-message" :class="settingsMessageKind">{{ settingsMessage }}</div>
                </article>
              </div>

              <aside class="settings-side">
                <article class="card security-card">
                  <div class="security-mark"><ShieldCheck :size="22" /></div>
                  <h3>密钥安全</h3>
                  <p>API Key 由服务端加密后存储在 PostgreSQL，浏览器只接收掩码。请勿把真实密钥写入代码或提交到 Git。</p>
                  <ul>
                    <li><CircleCheckBig :size="14" />管理员权限校验</li>
                    <li><CircleCheckBig :size="14" />数据库密文存储</li>
                    <li><CircleCheckBig :size="14" />仅发送聚合调度指标</li>
                  </ul>
                </article>
                <article class="card connection-card">
                  <span>连接状态</span>
                  <strong :class="aiConfig?.last_test_status ?? 'untested'">
                    <i />{{ aiConfig?.last_test_status === 'success' ? '连接正常' : aiConfig?.last_test_status === 'failed' ? '连接失败' : '尚未测试' }}
                  </strong>
                  <p>{{ aiConfig?.last_test_message ?? '保存配置后可发起最小化请求验证模型服务。' }}</p>
                  <small v-if="aiConfig?.last_tested_at">最近测试：{{ new Date(aiConfig?.last_tested_at ?? '').toLocaleString('zh-CN') }}</small>
                </article>
                <article class="card data-boundary">
                  <h3>数据边界</h3>
                  <p>AI 只接收里程、成本、准时率及脱敏线路摘要，不发送 API Key、用户密码或数据库连接信息。</p>
                </article>
              </aside>
            </template>
          </div>
        </template>
      </section>

      <section v-else-if="activeView === 'execution'" class="content">
        <div class="page-heading">
          <div>
            <p class="eyebrow"><Sparkles :size="14" /> 县域物流 · 智能协同优化</p>
            <h1>{{ pageTitle }}</h1>
            <p>审批下发的车辆任务与驾驶员执行状态</p>
          </div>
        </div>
        <div v-if="error" class="error"><AlertTriangle :size="17" />{{ error }}</div>
        <ExecutionCenter @session-change="role => authenticated = role === 'admin'" />
      </section>

      <div v-else class="loader"><BrainCircuit :size="34" /><b>正在连接祁智运调度引擎</b><span>加载县域节点、订单与车辆约束...</span></div>
    </main>
    <OperationGuide
      :open="guideOpen"
      :step="guideSteps[guideIndex]"
      :current="guideIndex"
      :total="guideSteps.length"
      @next="advanceOperationGuide"
      @previous="previousOperationGuide"
      @close="finishOperationGuide"
    />
  </div>
</template>

<style>
:root { font-family: Inter, "Microsoft YaHei", "PingFang SC", sans-serif; color:#17231d; background:#f3f5f2; font-synthesis:none }
* { box-sizing:border-box }
body { margin:0; min-width:0; min-height:100vh }
button { font:inherit }
.app-shell { display:flex; min-height:100vh }
.sidebar { position:fixed; inset:0 auto 0 0; width:214px; padding:24px 15px 18px; background:#092f20; color:#dce9e2; display:flex; flex-direction:column; z-index:20; box-shadow:8px 0 30px rgba(14,52,35,.12) }
.brand { display:flex; align-items:center; gap:11px; padding:0 9px 26px }
.brand-mark { width:40px; height:40px; display:grid; place-items:center; border-radius:12px; color:#103d2a; background:#f4b338 }
.brand strong { display:block; font-size:21px; letter-spacing:2px; color:#fff }
.brand span { display:block; margin-top:2px; font-size:8px; letter-spacing:2.3px; color:#8daf9d }
nav { display:flex; flex-direction:column; gap:5px }
.nav-item { width:100%; border:0; background:transparent; color:#a9c3b5; display:flex; align-items:center; gap:12px; padding:11px 13px; border-radius:9px; cursor:pointer; text-align:left }
.nav-item:hover,.nav-item.active { color:#fff; background:#18573a }
.nav-item i { margin-left:auto; display:grid; place-items:center; width:19px; height:19px; border-radius:99px; font-size:10px; font-style:normal; color:#fff; background:#df5d54 }
.side-bottom { margin-top:auto }
.operator { border-top:1px solid #24513d; margin-top:10px; padding:18px 7px 0; display:flex; align-items:center; gap:10px }
.operator > div { width:34px; height:34px; display:grid; place-items:center; border-radius:50%; background:#eeb142; color:#183b29; font-weight:800 }
.operator p { margin:0 }
.operator strong,.operator span { display:block }
.operator strong { font-size:12px; color:#f7fbf8 }.operator span { font-size:10px; color:#7fa28f; margin-top:3px }
.app-shell > main { width:calc(100% - 214px); margin-left:214px }
.topbar { height:58px; padding:0 24px; display:flex; align-items:center; justify-content:space-between; background:#fff; border-bottom:1px solid #e3e8e3 }
.crumb,.top-status,.top-status span { display:flex; align-items:center; gap:8px }
.crumb { color:#8a928e; font-size:12px }.crumb b { color:#2b3931 }.top-status { color:#78817c; font-size:11px; gap:18px }
.weather-status small{padding:2px 6px;border-radius:99px;background:#edf6f1;color:#17724a;font-size:9px}
.top-guide{height:34px;display:flex;align-items:center;gap:7px;padding:0 10px;border:1px solid #d5e4da;border-radius:8px;background:#f1f8f4;color:#176f48;font-weight:700;cursor:pointer}.top-guide:hover{border-color:#aacbb7;background:#e7f3eb}
.top-user{height:34px;display:flex;align-items:center;gap:8px;padding:0 10px;border:1px solid #dce4de;border-radius:8px;background:#fff;color:#52635a;cursor:pointer}.top-user:hover{border-color:#bdcec3;color:#146c47}
.online i,.live i { width:7px; height:7px; border-radius:50%; background:#24a869; box-shadow:0 0 0 4px #dff4e9 }
.content { padding:20px 24px 24px; max-width:1720px; margin:0 auto }
.page-heading { display:flex; align-items:flex-end; justify-content:space-between; margin-bottom:16px }
.eyebrow { color:#1c8050!important; font-weight:700; display:flex; align-items:center; gap:5px }
.page-heading h1 { margin:4px 0 4px; font-size:24px; color:#123324; letter-spacing:.5px }
.page-heading p { margin:0; color:#7c8680; font-size:12px }
.primary { display:flex; align-items:center; gap:7px; border:0; padding:10px 16px; color:#fff; background:#17794a; border-radius:9px; cursor:pointer; box-shadow:0 6px 16px rgba(23,121,74,.17) }
.primary:hover { background:#11653d }.primary:disabled { opacity:.65 }.primary.danger { background:#c94d48 }
.spin { animation:spin 1s linear infinite } @keyframes spin { to { transform:rotate(360deg) } }
.error { display:flex; gap:8px; padding:10px 14px; margin-bottom:12px; background:#fff1ef; color:#b33c35; border:1px solid #f1cfcc; border-radius:9px }
.workspace { display:grid; grid-template-columns:minmax(0,1fr); gap:14px }
.card { background:#fff; border:1px solid #e4e9e4; border-radius:14px; box-shadow:0 3px 12px rgba(30,58,43,.035) }
.map-card { position:relative; padding:0; min-height:720px; overflow:hidden }
.card-title,.result-head { display:flex; align-items:flex-start; justify-content:space-between }
.card-title h2,.result-head h2,.delta h2 { margin:0; color:#203a2d; font-size:14px }.card-title p,.result-head p { margin:4px 0 0; color:#8a928e; font-size:10px }
.legend { display:flex; gap:12px; color:#758079; font-size:9px }.legend span { display:flex; align-items:center; gap:5px }.legend i { width:7px; height:7px; border-radius:50% }.green{background:#166d43}.amber{background:#f3ad2d}.blue{background:#3c70d9}
.map-badge { position:absolute; left:26px; bottom:22px; display:flex; align-items:center; gap:6px; padding:7px 9px; font-size:9px; color:#466052; background:rgba(255,255,255,.88); border:1px solid #dce5dd; border-radius:7px; backdrop-filter:blur(6px) }
.right-stack { display:grid; grid-template-columns:.8fr 1fr 1.35fr; gap:12px; align-items:stretch }
.event-side { display:flex; flex-direction:column; gap:12px }
.score { padding:14px 16px; background:linear-gradient(135deg,#0e482f,#14643f); color:#fff; border:0 }
.score-top,.score-foot { display:flex; align-items:center; justify-content:space-between }.score-top span { font-size:11px; color:#c6dbd0 }.score-top b { font-size:28px }.score-top small{font-size:10px;color:#9fc3af}.score-bar{height:5px;background:#2b7453;border-radius:4px;margin:7px 0 9px}.score-bar i{display:block;height:100%;background:#f4b438;border-radius:4px;transition:width .35s ease}.score-foot{font-size:9px;color:#c6dbd0}.score-foot span{display:flex;align-items:center;gap:4px}.score-foot strong{color:#f8c55d}
.control,.routes,.process,.delta,.ai-note { padding:15px }
.control .card-title > svg,.routes .card-title > svg,.process .card-title > svg { color:#1d8050 }
.control-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:13px 0 }
.control-grid div { background:#f5f7f4; border-radius:9px; padding:10px }.control-grid span{font-size:9px;color:#859089;display:block}.control-grid b{font-size:19px;color:#163d29}.control-grid small{font-size:9px;margin-left:3px;color:#829087}
.simulate { width:100%; display:flex; align-items:center; justify-content:center; gap:6px; padding:9px; border:1px solid #efc9c6; border-radius:8px; background:#fff7f6; color:#b24a43; cursor:pointer; font-size:11px }
.routes { min-height:0 }.routes > button { width:100%; border:1px solid transparent; background:transparent; display:grid; grid-template-columns:4px 1fr auto; align-items:center; gap:9px; padding:9px 7px; border-radius:8px; text-align:left; cursor:pointer }.routes > button:hover,.routes > button.selected{background:#f3f7f3;border-color:#dfe9e0}.route-color{height:30px;border-radius:3px}.routes button strong,.routes button span{display:block}.routes button strong{font-size:11px;color:#314138}.routes button span{font-size:9px;color:#8b938e;margin-top:3px}.routes button>b{font-size:14px;color:#193c2a}.routes button small{font-size:8px;color:#929a95;margin-left:2px}
.bottom-grid { display:grid; grid-template-columns:minmax(650px,1fr) 330px; gap:14px; margin-top:14px }.result-card,.route-detail{padding:14px 16px}.result-head{margin-bottom:11px}.result-head>span{display:flex;align-items:center;gap:4px;padding:5px 8px;border-radius:20px;background:#e8f4ec;color:#1c7b4b;font-size:9px}
.route-detail { display:grid; grid-template-columns:repeat(3,1fr); gap:11px }.route-detail div{padding-right:8px;border-right:1px solid #edf0ed}.route-detail div:last-child{grid-column:1/-1;border:0}.route-detail span,.route-detail strong{display:block}.route-detail span{font-size:9px;color:#8a938e}.route-detail strong{font-size:14px;color:#173c29;margin-top:5px}.route-detail p{margin:5px 0 0;font-size:10px;color:#596860;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.event-grid { display:grid; grid-template-columns:minmax(620px,1fr) 360px; gap:14px }.event-map{min-height:700px}.live{display:flex;align-items:center;gap:7px;color:#168151;font-size:10px;font-weight:800}
.event-alert { display:flex; gap:12px; padding:16px; color:#fff; background:linear-gradient(135deg,#b8413c,#d96555); border-radius:14px; box-shadow:0 8px 20px rgba(178,65,60,.17) }.event-alert span{font-size:9px;text-transform:uppercase;letter-spacing:1px}.event-alert h2{font-size:14px;margin:4px 0}.event-alert p{font-size:9px;margin:0;color:#f8d7d2}
.event-alert.resolved{background:#126b45;box-shadow:0 8px 20px rgba(18,107,69,.14)}.event-alert.resolved p{color:#d6eee2}
.progress{height:5px;background:#e7ece8;border-radius:8px;margin:14px 0}.progress i{display:block;height:100%;background:#228652;border-radius:8px;transition:width .5s}
.process ol{list-style:none;margin:0;padding:0}.process li{display:flex;gap:9px;padding:8px 0;border-bottom:1px solid #edf0ed;opacity:.52}.process li:last-child{border:0}.process li svg{color:#8d9992}.process li.done{opacity:1}.process li.done svg{color:#188050}.process b,.process span{display:block}.process b{font-size:10px;color:#304239}.process span{font-size:9px;color:#88918c;margin-top:3px}
.delta h2{margin-bottom:8px}.delta div{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #edf0ed;font-size:10px;color:#7e8982}.delta div:last-child{border:0}.delta b{color:#263c30}.amber-text{color:#c07a0b!important}.green-text{color:#188050!important}
.ai-note{background:#fff}.decision-evidence-head{display:flex;align-items:flex-start;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid #e5ebe7}.decision-evidence-head>span{display:flex;align-items:center;gap:5px;color:#176f47;font-size:11px;font-weight:750}.decision-evidence-head small{font-size:8px;color:#859188}.decision-evidence-list{display:grid;gap:0}.decision-evidence-list>div{display:grid;grid-template-columns:23px 1fr;gap:8px;padding:9px 0;border-bottom:1px solid #edf1ee}.decision-evidence-list>div:last-child{border:0}.decision-evidence-list i{width:22px;height:22px;display:grid;place-items:center;border-radius:6px;background:#eaf5ef;color:#17784a;font-style:normal}.decision-evidence-list>div.risk i{background:#fff1e6;color:#c97718}.decision-evidence-list p{margin:0;line-height:1.45}.decision-evidence-list b,.decision-evidence-list span{display:block}.decision-evidence-list b{font-size:9px;color:#263b30;margin-bottom:3px}.decision-evidence-list span{font-size:8px;color:#718077}.decision-empty{margin:11px 0 0!important;font-size:9px!important;line-height:1.6!important;color:#78877f!important}
.history-layout{display:flex;flex-direction:column;gap:14px}.history-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;overflow:hidden}.history-summary>div{display:grid;grid-template-columns:auto 1fr;align-items:center;column-gap:10px;padding:18px 20px;border-right:1px solid #e7ebe7}.history-summary>div:last-child{border:0}.history-summary svg{grid-row:1/3;color:#1d8050}.history-summary span{font-size:10px;color:#849089}.history-summary b{font-size:19px;color:#173c29;margin-top:3px}.history-table-card{padding:18px}.db-state{display:flex;align-items:center;gap:7px;color:#1c8050;font-size:10px}.db-state i,.status-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#23a568;box-shadow:0 0 0 3px #e0f3e8}.history-table{margin-top:16px;border:1px solid #e8ece8;border-radius:10px;overflow:hidden}.history-row{display:grid;grid-template-columns:1.2fr .9fr .65fr .7fr .7fr .55fr .75fr 1.25fr .55fr;align-items:center;min-height:48px;padding:0 14px;border-bottom:1px solid #edf0ed;font-size:10px;color:#5d6b63}.history-row:last-child{border:0}.history-row strong{font-family:Consolas,monospace;color:#1d5639}.history-head{min-height:38px;background:#f4f7f4;color:#7f8a84;font-weight:700}.history-row span:nth-child(3){display:flex;align-items:center;gap:6px}.history-empty{padding:45px;text-align:center;color:#8b948f;font-size:11px}.row-action{display:flex;align-items:center;justify-content:center;gap:3px;border:1px solid #cfe1d5;border-radius:6px;padding:5px 6px;background:#f2f8f4;color:#19794b;font-size:9px;cursor:pointer}.row-action:hover{background:#e5f2e9}.row-action:disabled{opacity:.55}.history-ai-result{padding:17px 19px;background:linear-gradient(135deg,#eff7f1,#fffaf0)}.ai-result-head{display:flex;align-items:center;justify-content:space-between}.ai-result-head>div{display:flex;align-items:center;gap:7px;color:#17794a;font-size:12px;font-weight:800}.ai-result-head small{font-size:8px;color:#859089}.history-ai-result p{margin:10px 0 0;font-size:11px;line-height:1.85;color:#53645a;white-space:pre-line}
.scenario-layout{display:flex;flex-direction:column;gap:14px}.import-card{display:grid;grid-template-columns:auto minmax(300px,1fr) minmax(220px,300px) auto;align-items:center;gap:16px;padding:20px}.import-icon{width:48px;height:48px;display:grid;place-items:center;border-radius:13px;background:#e8f4ec;color:#17794a}.import-copy .eyebrow{margin:0 0 3px}.import-copy h2{font-size:15px;color:#173c29;margin:0}.import-copy p:last-child{font-size:9px;color:#7e8982;margin:5px 0 0;line-height:1.5}.file-picker{height:42px;display:flex;align-items:center;gap:8px;padding:0 12px;border:1px dashed #a9c4b3;border-radius:9px;background:#f7faf8;color:#4f685a;font-size:10px;cursor:pointer;overflow:hidden}.file-picker span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.file-picker input{display:none}.scenario-message{margin:0}.version-card{padding:19px}.version-list{margin-top:15px;border:1px solid #e5ebe7;border-radius:10px;overflow:hidden}.version-row{display:grid;grid-template-columns:90px minmax(210px,1.5fr) 65px 65px 65px 130px 76px;align-items:center;gap:10px;min-height:66px;padding:0 14px;border-bottom:1px solid #e9eeea;background:#fff}.version-row:last-child{border:0}.version-row.active{background:#f1f8f3}.version-status{display:flex;align-items:center;gap:7px;font-size:9px;color:#7d8982}.version-status i{width:7px;height:7px;border-radius:50%;background:#a6aea9}.version-row.active .version-status{color:#16804d;font-weight:700}.version-row.active .version-status i{background:#23a568;box-shadow:0 0 0 3px #dff2e7}.version-name strong,.version-name span,.version-count b,.version-count span,.version-source span,.version-source small{display:block}.version-name strong{font-size:11px;color:#263d30}.version-name span{font-size:8px;color:#89938d;margin-top:4px}.version-count{text-align:center}.version-count b{font-size:14px;color:#1a5e3c}.version-count span{font-size:8px;color:#8b948f;margin-top:2px}.version-source span{font-size:9px;color:#52655a}.version-source small{font-size:8px;color:#929a95;margin-top:4px}.activate-button{justify-content:center;padding:7px 9px;font-size:9px}
.settings-layout{display:grid;grid-template-columns:minmax(620px,1fr) 310px;gap:14px;align-items:start}.settings-main,.settings-side{display:flex;flex-direction:column;gap:14px}.ai-config-card{padding:22px}.settings-title{padding-bottom:18px;border-bottom:1px solid #e8ece8}.settings-title h2{font-size:18px;margin:5px 0}.settings-title .eyebrow{margin:0}.text-button{display:flex;align-items:center;gap:5px;border:0;background:transparent;color:#78867e;font-size:10px;cursor:pointer}.text-button:hover{color:#b64b45}.ai-form{margin-top:20px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:17px 18px}.form-grid label{display:flex;flex-direction:column;gap:7px}.form-grid label>span{font-size:10px;font-weight:700;color:#4b5d53}.form-grid label>span>b{float:right;color:#198050}.form-grid input:not([type="range"]):not([type="checkbox"]),.form-grid select,.admin-login input{width:100%;height:40px;border:1px solid #dce4de;border-radius:8px;padding:0 11px;background:#fbfcfb;color:#243b2f;outline:none}.form-grid input:focus,.form-grid select:focus,.admin-login input:focus{border-color:#2b8b5c;box-shadow:0 0 0 3px #e7f4ec}.span-two{grid-column:1/-1}.secret-field{position:relative}.secret-field svg{position:absolute;left:12px;top:13px;color:#799087}.secret-field input{padding-left:36px!important}.form-grid small{font-size:9px;color:#8b958f;line-height:1.5}.form-grid input[type="range"]{accent-color:#1b8050}.switch-row{flex-direction:row!important;align-items:center;justify-content:space-between;padding:3px 0}.switch-row span{display:flex;flex-direction:column;gap:4px}.switch-row input{width:38px;height:20px;accent-color:#1b8050}.form-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:24px;padding-top:17px;border-top:1px solid #edf0ed}.secondary{display:flex;align-items:center;gap:6px;border:1px solid #cfdcd3;padding:9px 14px;border-radius:9px;background:#fff;color:#296246;cursor:pointer}.secondary:hover{background:#f1f7f3}.secondary:disabled{opacity:.5;cursor:not-allowed}.settings-message{margin-top:14px;padding:10px 12px;border-radius:8px;font-size:10px}.settings-message.success{color:#176c43;background:#e8f5ed;border:1px solid #cde9d8}.settings-message.error{color:#a9403b;background:#fff0ef;border:1px solid #f0d0cd}.settings-message.info{color:#536b5e;background:#f1f5f2;border:1px solid #e0e7e2}.security-card,.connection-card,.data-boundary{padding:18px}.security-card{background:linear-gradient(145deg,#0d3d29,#145d3b);color:#fff;border:0}.security-mark{width:42px;height:42px;display:grid;place-items:center;border-radius:11px;color:#153b29;background:#f0b643}.security-card h3,.data-boundary h3{font-size:13px;margin:12px 0 7px}.security-card p,.data-boundary p,.connection-card p{font-size:9px;line-height:1.7;margin:0;color:#bfd4c8}.security-card ul{list-style:none;padding:13px 0 0;margin:13px 0 0;border-top:1px solid #2e674d}.security-card li{display:flex;align-items:center;gap:7px;margin-top:8px;font-size:9px;color:#e6f0eb}.security-card li svg{color:#f2ba4a}.connection-card>span{display:block;font-size:9px;color:#849089}.connection-card>strong{display:flex;align-items:center;gap:7px;margin:8px 0;font-size:14px;color:#8a928d}.connection-card>strong i{width:8px;height:8px;border-radius:50%;background:#9ca5a0}.connection-card>strong.success{color:#16804d}.connection-card>strong.success i{background:#23a568;box-shadow:0 0 0 4px #e0f3e8}.connection-card>strong.failed{color:#bc4943}.connection-card>strong.failed i{background:#d75850;box-shadow:0 0 0 4px #f8e5e3}.connection-card p,.data-boundary p{color:#6d7a72}.connection-card small{display:block;margin-top:10px;font-size:8px;color:#929a95}.data-boundary{background:#fffaf0;border-color:#f0e3c8}.admin-login{grid-column:1/-1;width:430px;margin:55px auto;padding:30px}.login-icon{width:52px;height:52px;display:grid;place-items:center;border-radius:14px;background:#e9f4ed;color:#17794a}.admin-login .eyebrow{margin:18px 0 5px}.admin-login h2{margin:0;color:#173c29;font-size:21px}.login-copy{font-size:10px;color:#7b8780;line-height:1.7;margin:9px 0 20px}.admin-login form{display:flex;flex-direction:column;gap:14px}.admin-login label{display:flex;flex-direction:column;gap:7px}.admin-login label span{font-size:10px;font-weight:700;color:#4b5d53}.login-submit{margin-top:4px;justify-content:center;width:100%}
.loader { height:calc(100vh - 58px); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:10px;color:#1b7047}.loader b{color:#234334}.loader span{font-size:11px;color:#87918b}
@media(max-width:1250px){.bottom-grid,.event-grid{grid-template-columns:minmax(600px,1fr) 300px}.right-stack{grid-template-columns:1fr 1fr}.right-stack .routes{grid-column:1/-1}.settings-layout{grid-template-columns:minmax(560px,1fr) 280px}.import-card{grid-template-columns:auto 1fr 240px}.import-card>.primary{grid-column:3}.version-row{grid-template-columns:80px minmax(180px,1fr) 55px 55px 55px 110px 68px}.sidebar{width:190px}.app-shell > main{width:calc(100% - 190px);margin-left:190px}}
@media(max-width:760px){
  .sidebar{width:68px;padding:16px 8px 14px}
  .brand{justify-content:center;padding:0 0 18px}.brand>div:last-child,.nav-item span,.nav-item i,.operator p{display:none}
  .brand-mark{width:38px;height:38px}.nav-item{justify-content:center;padding:11px 8px}.operator{justify-content:center;padding:14px 0 0}
  .app-shell > main{width:calc(100% - 68px);margin-left:68px}
  .topbar{height:54px;padding:0 12px}.top-status>span{display:none}.top-status{gap:6px}.top-user,.top-guide{padding:0 8px}.top-guide span{display:none}.crumb{gap:5px}
  .content{padding:16px 12px 20px}
  .workspace,.bottom-grid,.event-grid{grid-template-columns:minmax(0,1fr)}
  .right-stack{display:flex;flex-direction:column;min-width:0}.right-stack .routes{grid-column:auto}.event-side{min-width:0}
  .page-heading{align-items:flex-start;gap:12px;flex-direction:column}
  .page-heading>.primary{width:100%;justify-content:center}
}
</style>
