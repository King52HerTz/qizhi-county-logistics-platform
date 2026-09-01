<script setup lang="ts">
import {
  ArrowRight, CheckCheck, CircleCheckBig, ClipboardCheck,
  Download, KeyRound, LogOut, MapPin, Navigation, PackageCheck,
  Play, Route, ShieldCheck, Truck,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  advanceDriverAssignment, approveDispatchPlan, clearAdminSession,
  downloadDispatchReport, getDispatchPlans, getDriverAssignments,
  getRunHistory, getSessionRole, hasSession, issueDispatchPlan, login,
  submitDispatchPlan,
} from '../services/api'
import type {
  DispatchPlanView, DriverAssignmentView, RunSummary,
} from '../types/logistics'

const emit = defineEmits<{ sessionChange: [role: string] }>()
const role = ref(getSessionRole())
const loggedIn = ref(hasSession())
const busy = ref(false)
const message = ref('')
const messageKind = ref<'success' | 'error' | 'info'>('info')
const plans = ref<DispatchPlanView[]>([])
const assignments = ref<DriverAssignmentView[]>([])
const runs = ref<RunSummary[]>([])
const form = reactive({ username: '', password: '' })

const latestRun = computed(() => runs.value.find(item => item.status !== 'infeasible'))
const latestPlan = computed(() => {
  const runId = latestRun.value?.run_id
  return plans.value.find(item => item.run_id === runId) ?? plans.value[0]
})
const activeAssignments = computed(() =>
  assignments.value.filter(item => item.status !== 'completed'))
const statusLabel: Record<string, string> = {
  pending_approval: '待审批',
  approved: '已批准',
  rejected: '已驳回',
  dispatched: '已下发',
  accepted: '已接单',
  executing: '执行中',
  completed: '已完成',
  pending: '待接单',
}
const planSteps = [
  ['pending_approval', '提交审批'],
  ['approved', '审核通过'],
  ['dispatched', '任务下发'],
  ['accepted', '司机接单'],
  ['executing', '配送执行'],
  ['completed', '完成归档'],
]
const statusRank: Record<string, number> = {
  pending_approval: 0, approved: 1, dispatched: 2, accepted: 3, executing: 4, completed: 5,
}

async function loadWorkspace() {
  if (!loggedIn.value) return
  busy.value = true
  try {
    if (role.value === 'driver') {
      assignments.value = (await getDriverAssignments()).items
    } else {
      const [planResult, runResult] = await Promise.all([getDispatchPlans(), getRunHistory()])
      plans.value = planResult.items
      runs.value = runResult.items
    }
  } catch (cause) {
    messageKind.value = 'error'
    message.value = cause instanceof Error ? cause.message : '执行中心加载失败'
  } finally {
    busy.value = false
  }
}

async function signIn() {
  busy.value = true
  message.value = ''
  try {
    const response = await login(form.username, form.password)
    if (!['admin', 'dispatcher', 'driver'].includes(response.role)) {
      throw new Error('当前账号没有执行中心权限')
    }
    role.value = response.role
    loggedIn.value = true
    form.password = ''
    messageKind.value = 'success'
    message.value = response.role === 'driver' ? '驾驶员身份验证成功' : '调度管理身份验证成功'
    emit('sessionChange', response.role)
    await loadWorkspace()
  } catch (cause) {
    clearAdminSession()
    role.value = ''
    loggedIn.value = false
    messageKind.value = 'error'
    message.value = cause instanceof Error ? cause.message : '登录失败'
  } finally {
    busy.value = false
  }
}

function signOut() {
  clearAdminSession()
  role.value = ''
  loggedIn.value = false
  plans.value = []
  assignments.value = []
  messageKind.value = 'info'
  message.value = '已安全退出执行中心'
  emit('sessionChange', '')
}

async function runPlanAction(action: 'submit' | 'approve' | 'dispatch') {
  busy.value = true
  message.value = ''
  try {
    if (action === 'submit') {
      if (!latestRun.value) throw new Error('暂无可提交的求解方案')
      await submitDispatchPlan(latestRun.value.run_id)
      message.value = '方案已提交审批'
    } else if (action === 'approve') {
      if (!latestPlan.value) throw new Error('暂无待审批方案')
      await approveDispatchPlan(latestPlan.value.id)
      message.value = '审批通过，可下发驾驶员'
    } else {
      if (!latestPlan.value) throw new Error('暂无可下发方案')
      await issueDispatchPlan(latestPlan.value.id)
      message.value = '车辆任务已下发驾驶员'
    }
    messageKind.value = 'success'
    await loadWorkspace()
  } catch (cause) {
    messageKind.value = 'error'
    message.value = cause instanceof Error ? cause.message : '操作失败'
  } finally {
    busy.value = false
  }
}

async function runAssignmentAction(
  assignment: DriverAssignmentView,
  action: 'accept' | 'start' | 'complete',
) {
  busy.value = true
  try {
    await advanceDriverAssignment(assignment.id, action)
    messageKind.value = 'success'
    message.value = {
      accept: `已接收 ${assignment.plate} 配送任务`,
      start: `${assignment.plate} 已发车`,
      complete: `${assignment.plate} 已完成配送`,
    }[action]
    await loadWorkspace()
  } catch (cause) {
    messageKind.value = 'error'
    message.value = cause instanceof Error ? cause.message : '任务状态更新失败'
  } finally {
    busy.value = false
  }
}

function formatArrivalMinute(minute: number) {
  const normalized = Math.max(0, minute)
  const hours = Math.floor(normalized / 60) % 24
  const minutes = normalized % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

function openNavigation(assignment: DriverAssignmentView) {
  const stop = assignment.next_stop
  if (!stop) {
    messageKind.value = 'info'
    message.value = '当前任务没有待导航站点'
    return
  }

  const target = `${stop.longitude.toFixed(6)},${stop.latitude.toFixed(6)},${encodeURIComponent(stop.node_name)}`
  const navigationUrl = new URL('https://uri.amap.com/navigation')
  navigationUrl.searchParams.set('to', target)
  navigationUrl.searchParams.set('mode', 'car')
  navigationUrl.searchParams.set('policy', '0')
  navigationUrl.searchParams.set('src', 'qizhi-logistics')
  navigationUrl.searchParams.set('callnative', '0')
  const opened = window.open(navigationUrl.toString(), '_blank', 'noopener,noreferrer')
  if (!opened) {
    window.location.assign(navigationUrl.toString())
  }
  messageKind.value = 'success'
  message.value = `已打开高德导航：${stop.node_name}`
}

async function saveReport(plan: DispatchPlanView) {
  try {
    const blob = await downloadDispatchReport(plan.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `祁智运调度执行报告-${plan.id}.html`
    link.click()
    URL.revokeObjectURL(url)
    messageKind.value = 'success'
    message.value = '执行报告已导出，可用浏览器打印为 PDF'
  } catch (cause) {
    messageKind.value = 'error'
    message.value = cause instanceof Error ? cause.message : '报告导出失败'
  }
}

onMounted(loadWorkspace)
</script>

<template>
  <div class="execution-center" data-guide="execution-workspace">
    <article v-if="!loggedIn" class="execution-login">
      <div class="login-visual"><ClipboardCheck :size="30" /></div>
      <div class="login-copy">
        <h2>进入调度执行中心</h2>
        <p>管理员负责审批和下发，驾驶员负责接单、发车与完成确认。</p>
      </div>
      <form @submit.prevent="signIn">
        <label><span>账号</span><input v-model.trim="form.username" autocomplete="username" required /></label>
        <label><span>密码</span><input v-model="form.password" type="password" autocomplete="current-password" required /></label>
        <button class="execution-primary" :disabled="busy"><KeyRound :size="16" />{{ busy ? '正在验证' : '登录执行中心' }}</button>
      </form>
      <p class="demo-account">调度管理：admin　|　驾驶员：driver</p>
      <div v-if="message" class="execution-message" :class="messageKind">{{ message }}</div>
    </article>

    <template v-else-if="role !== 'driver'">
      <div class="execution-toolbar">
        <div><ShieldCheck :size="19" /><span>调度管理工作台</span><b>{{ role }}</b></div>
        <button @click="signOut"><LogOut :size="14" />退出</button>
      </div>
      <div v-if="message" class="execution-message" :class="messageKind">{{ message }}</div>

      <article class="execution-hero">
        <div>
          <p>当前执行批次</p>
          <h2>{{ latestPlan ? `执行单 #${latestPlan.id}` : '等待方案提交' }}</h2>
          <span>{{ latestPlan?.run_id ?? latestRun?.run_id ?? '请先生成一份可行调度方案' }}</span>
        </div>
        <div class="hero-metrics">
          <p><span>路线</span><b>{{ latestPlan?.route_count ?? 0 }}</b></p>
          <p><span>总里程</span><b>{{ latestPlan?.distance_km ?? 0 }}<small>km</small></b></p>
          <p><span>预计成本</span><b>¥{{ latestPlan?.estimated_cost_cny ?? 0 }}</b></p>
        </div>
        <button
          v-if="!latestPlan || latestPlan.run_id !== latestRun?.run_id"
          class="execution-primary"
          :disabled="busy || !latestRun"
          @click="runPlanAction('submit')"
        ><ClipboardCheck :size="16" />提交最新方案</button>
        <button
          v-else-if="latestPlan.status === 'pending_approval'"
          class="execution-primary"
          :disabled="busy"
          @click="runPlanAction('approve')"
        ><CheckCheck :size="16" />审核通过</button>
        <button
          v-else-if="latestPlan.status === 'approved'"
          class="execution-primary"
          :disabled="busy"
          @click="runPlanAction('dispatch')"
        ><Navigation :size="16" />下发驾驶员</button>
        <button v-else class="report-button" @click="saveReport(latestPlan)"><Download :size="16" />导出执行报告</button>
      </article>

      <article class="execution-flow">
        <div
          v-for="([step, label], index) in planSteps"
          :key="step"
          class="flow-step"
          :class="{ done: latestPlan && statusRank[latestPlan.status] >= index, current: latestPlan?.status === step }"
        >
          <span><CircleCheckBig v-if="latestPlan && statusRank[latestPlan.status] > index" :size="17" /><b v-else>{{ index + 1 }}</b></span>
          <p><strong>{{ label }}</strong><small>{{ latestPlan?.status === step ? statusLabel[step] : '流程节点' }}</small></p>
          <ArrowRight v-if="index < planSteps.length - 1" :size="15" />
        </div>
      </article>

      <div class="execution-grid">
        <article class="execution-list">
          <header><div><h2>车辆任务</h2><p>按求解路线生成并独立追踪驾驶员状态</p></div><span>{{ latestPlan?.assignments.length ?? 0 }} 条</span></header>
          <div v-for="item in latestPlan?.assignments" :key="item.id" class="assignment-row">
            <span class="truck-icon"><Truck :size="18" /></span>
            <div><strong>{{ item.plate }}</strong><small>{{ item.driver_username }} · {{ item.stop_count }} 站 · {{ item.load_kg }} kg</small></div>
            <p><b>{{ item.distance_km }} km</b><small>{{ item.duration_minutes }} 分钟</small></p>
            <span class="assignment-status" :class="item.status">{{ statusLabel[item.status] }}</span>
          </div>
          <div v-if="!latestPlan?.assignments.length" class="execution-empty">审批通过并下发后，这里将生成驾驶员任务。</div>
        </article>

        <aside class="audit-card">
          <Route :size="22" />
          <h3>流程可追溯</h3>
          <p>每一次提交、审批、下发和司机确认都记录操作人、时间与前后状态。</p>
          <ul>
            <li><CircleCheckBig :size="14" />审批与执行状态分离</li>
            <li><CircleCheckBig :size="14" />非法状态跳转自动拒绝</li>
            <li><CircleCheckBig :size="14" />完整执行报告可下载</li>
          </ul>
        </aside>
      </div>
    </template>

    <template v-else>
      <div class="execution-toolbar driver-toolbar">
        <div><Truck :size="19" /><span>驾驶员任务台</span><b>driver</b></div>
        <button @click="signOut"><LogOut :size="14" />退出</button>
      </div>
      <div v-if="message" class="execution-message" :class="messageKind">{{ message }}</div>
      <article class="driver-summary">
        <div><span>待执行任务</span><b>{{ activeAssignments.length }}</b></div>
        <div><span>待配送里程</span><b>{{ activeAssignments.reduce((sum,item)=>sum+item.distance_km,0).toFixed(1) }} km</b></div>
        <div><span>今日载重</span><b>{{ activeAssignments.reduce((sum,item)=>sum+item.load_kg,0) }} kg</b></div>
      </article>
      <div class="driver-task-grid">
        <article v-for="item in assignments" :key="item.id" class="driver-task" :class="item.status">
          <header><span><Truck :size="18" /></span><div><strong>{{ item.plate }}</strong><small>执行单 #{{ item.plan_id }} · 路线 {{ item.route_index + 1 }}</small></div><b>{{ statusLabel[item.status] }}</b></header>
          <div class="task-route"><MapPin :size="17" /><p><span>下一站 · 第 {{ item.next_stop?.sequence ?? '-' }} 站</span><strong>{{ item.next_stop_name ?? '配送中心' }}</strong><small v-if="item.next_stop">预计到达 {{ formatArrivalMinute(item.next_stop.arrival_minute) }} · {{ item.next_stop.load_kg }} kg</small></p></div>
          <div v-if="item.navigation_stops.length" class="task-stops">
            <div class="task-stops-heading"><span>配送节点</span><small>{{ item.navigation_stops.length }} 站</small></div>
            <ol>
              <li v-for="stop in item.navigation_stops" :key="`${item.id}-${stop.sequence}`" :class="{ current: stop.sequence === item.next_stop?.sequence, completed: stop.status === 'completed' }">
                <span>{{ stop.sequence }}</span><b>{{ stop.node_name }}</b>
              </li>
            </ol>
          </div>
          <dl>
            <div><dt>里程</dt><dd>{{ item.distance_km }} km</dd></div>
            <div><dt>停靠</dt><dd>{{ item.stop_count }} 站</dd></div>
            <div><dt>载重</dt><dd>{{ item.load_kg }} kg</dd></div>
            <div><dt>耗时</dt><dd>{{ item.duration_minutes }} 分钟</dd></div>
          </dl>
          <button v-if="item.status === 'pending'" :disabled="busy" @click="runAssignmentAction(item,'accept')"><PackageCheck :size="16" />确认接单</button>
          <div v-else-if="item.status === 'accepted'" class="driver-actions">
            <button class="driver-nav-button" :disabled="busy || !item.next_stop" @click="openNavigation(item)"><Navigation :size="16" />开始导航</button>
            <button :disabled="busy" @click="runAssignmentAction(item,'start')"><Play :size="16" />确认发车</button>
          </div>
          <div v-else-if="item.status === 'executing'" class="driver-actions">
            <button class="driver-nav-button" :disabled="busy || !item.next_stop" @click="openNavigation(item)"><Navigation :size="16" />继续导航</button>
            <button :disabled="busy" @click="runAssignmentAction(item,'complete')"><CheckCheck :size="16" />完成配送</button>
          </div>
          <div v-else class="task-complete"><CircleCheckBig :size="17" />配送已完成</div>
        </article>
        <div v-if="!assignments.length" class="execution-empty driver-empty">暂无已下发任务，请联系调度中心。</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.execution-center{display:flex;flex-direction:column;gap:14px}.execution-login{width:min(720px,100%);margin:30px auto;padding:30px;background:#fff;border:1px solid #e0e7e2;border-radius:15px;box-shadow:0 18px 45px rgba(22,65,41,.08);display:grid;grid-template-columns:64px 1fr;gap:8px 18px}.login-visual{grid-row:1/3;width:54px;height:54px;display:grid;place-items:center;border-radius:14px;background:#e8f5ee;color:#16834f}.login-copy h2{margin:2px 0 5px;font-size:20px;color:#133c28}.login-copy p{margin:0;color:#78867e;font-size:11px}.execution-login form{grid-column:1/3;display:grid;grid-template-columns:1fr 1fr auto;gap:12px;margin-top:20px}.execution-login label span{display:block;font-size:10px;color:#637169;margin-bottom:6px}.execution-login input{width:100%;height:40px;border:1px solid #dce4de;border-radius:8px;padding:0 11px;outline:none}.execution-primary,.report-button,.driver-task button{border:0;border-radius:8px;padding:0 15px;background:#14844d;color:#fff;display:flex;align-items:center;justify-content:center;gap:7px;font-weight:700;cursor:pointer;min-height:40px}.execution-primary:disabled,.driver-task button:disabled{opacity:.6}.demo-account{grid-column:1/3;margin:3px 0 0;color:#8a968f;font-size:10px}.execution-message{padding:10px 13px;border-radius:8px;font-size:11px}.execution-message.success{color:#157444;background:#eaf7ef}.execution-message.error{color:#b33e39;background:#fff0ee}.execution-message.info{color:#48675a;background:#edf4f0}.execution-login .execution-message{grid-column:1/3}.execution-toolbar{height:48px;padding:0 15px;background:#103f2a;color:#fff;border-radius:10px;display:flex;align-items:center;justify-content:space-between}.execution-toolbar>div,.execution-toolbar button{display:flex;align-items:center;gap:8px}.execution-toolbar b{font-size:9px;background:#f2b43f;color:#173a29;padding:3px 7px;border-radius:9px}.execution-toolbar button{border:0;background:transparent;color:#bcd2c6;cursor:pointer}.execution-hero{padding:20px 22px;background:linear-gradient(115deg,#0d4c31,#176f46);color:#fff;border-radius:13px;display:grid;grid-template-columns:1fr auto auto;gap:32px;align-items:center}.execution-hero p{margin:0 0 6px;color:#a9cdbb;font-size:10px}.execution-hero h2{margin:0 0 5px;font-size:23px}.execution-hero>div>span{color:#bad0c5;font-size:10px}.hero-metrics{display:flex;gap:30px}.hero-metrics p{min-width:72px}.hero-metrics span,.hero-metrics b{display:block}.hero-metrics b{font-size:20px;color:#fff;margin-top:5px}.hero-metrics small{font-size:9px;margin-left:3px}.execution-hero .execution-primary,.execution-hero .report-button{background:#f2b43f;color:#153a29}.execution-flow{display:grid;grid-template-columns:repeat(6,1fr);padding:17px 20px;background:#fff;border:1px solid #e2e8e3;border-radius:12px}.flow-step{position:relative;display:flex;align-items:center;gap:8px;color:#9aa59f}.flow-step>span{width:28px;height:28px;display:grid;place-items:center;border-radius:50%;background:#edf1ee}.flow-step p{margin:0}.flow-step strong,.flow-step small{display:block}.flow-step strong{font-size:10px}.flow-step small{font-size:8px;margin-top:3px}.flow-step>svg{position:absolute;right:8px;color:#cad3cd}.flow-step.done{color:#17834f}.flow-step.done>span{color:#fff;background:#17834f}.flow-step.current strong{color:#16452e}.execution-grid{display:grid;grid-template-columns:minmax(650px,1fr) 285px;gap:14px}.execution-list,.audit-card{background:#fff;border:1px solid #e2e8e3;border-radius:12px}.execution-list{padding:17px}.execution-list header{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:12px;border-bottom:1px solid #e8ece9}.execution-list h2{margin:0;font-size:15px}.execution-list header p{margin:4px 0 0;color:#849087;font-size:9px}.execution-list header>span{font-size:9px;color:#17834f;background:#eaf6ef;padding:5px 8px;border-radius:7px}.assignment-row{display:grid;grid-template-columns:38px 1fr 100px 72px;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid #edf0ee}.truck-icon{width:34px;height:34px;display:grid;place-items:center;color:#16834f;background:#eaf6ef;border-radius:8px}.assignment-row strong,.assignment-row small{display:block}.assignment-row strong{font-size:11px}.assignment-row small{color:#849087;font-size:8px;margin-top:4px}.assignment-row p{margin:0}.assignment-row p b{font-size:11px}.assignment-status{text-align:center;font-size:9px;padding:5px 7px;border-radius:7px;background:#eef2ef;color:#637169}.assignment-status.accepted,.assignment-status.executing{background:#e9f3ff;color:#2878d0}.assignment-status.completed{background:#e9f6ee;color:#17834f}.audit-card{padding:22px;color:#315143}.audit-card>svg{color:#17834f}.audit-card h3{margin:12px 0 7px}.audit-card p{font-size:10px;line-height:1.7;color:#77857d}.audit-card ul{list-style:none;padding:12px 0 0;margin:14px 0 0;border-top:1px solid #e6ebe7}.audit-card li{display:flex;gap:6px;margin:9px 0;font-size:9px;color:#587064}.audit-card li svg{color:#17834f}.execution-empty{padding:30px;text-align:center;color:#8a968f;font-size:10px}.driver-toolbar{background:#143f5f}.driver-summary{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border:1px solid #e1e7e2;border-radius:12px}.driver-summary>div{padding:17px 22px;border-right:1px solid #e6ebe7}.driver-summary>div:last-child{border:0}.driver-summary span,.driver-summary b{display:block}.driver-summary span{font-size:10px;color:#7b8981}.driver-summary b{font-size:20px;color:#16462f;margin-top:6px}.driver-task-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.driver-task{padding:17px;background:#fff;border:1px solid #e0e7e2;border-top:4px solid #f2b43f;border-radius:12px}.driver-task.accepted{border-top-color:#2878d0}.driver-task.executing{border-top-color:#17834f}.driver-task.completed{border-top-color:#91a199}.driver-task header{display:flex;align-items:center;gap:9px}.driver-task header>span{width:35px;height:35px;display:grid;place-items:center;background:#edf5f0;color:#17834f;border-radius:9px}.driver-task header div{flex:1}.driver-task header strong,.driver-task header small{display:block}.driver-task header strong{font-size:12px}.driver-task header small{font-size:8px;color:#849087;margin-top:4px}.driver-task header>b{font-size:9px;color:#5c6b63}.task-route{display:flex;align-items:center;gap:9px;margin:16px 0;padding:12px;background:#f2f6f3;border-radius:9px;color:#17834f}.task-route p{margin:0}.task-route span,.task-route strong{display:block}.task-route span{font-size:8px;color:#7d8982}.task-route strong{font-size:11px;margin-top:3px}.driver-task dl{display:grid;grid-template-columns:1fr 1fr;margin:0 0 14px}.driver-task dl>div{padding:8px;border-bottom:1px solid #edf0ee}.driver-task dt{font-size:8px;color:#88948d}.driver-task dd{margin:4px 0 0;font-size:10px;font-weight:700}.driver-task button{width:100%}.task-complete{height:40px;display:flex;align-items:center;justify-content:center;gap:6px;border-radius:8px;color:#17834f;background:#eaf6ef;font-size:10px}.driver-empty{grid-column:1/4;background:#fff;border-radius:12px}
.execution-center{display:flex;flex-direction:column;gap:14px}.execution-login{width:min(720px,100%);margin:30px auto;padding:30px;background:#fff;border:1px solid #e0e7e2;border-radius:15px;box-shadow:0 18px 45px rgba(22,65,41,.08);display:grid;grid-template-columns:64px 1fr;gap:8px 18px}.login-visual{grid-row:1/3;width:54px;height:54px;display:grid;place-items:center;border-radius:14px;background:#e8f5ee;color:#16834f}.login-copy h2{margin:2px 0 5px;font-size:20px;color:#133c28}.login-copy p{margin:0;color:#78867e;font-size:11px}.execution-login form{grid-column:1/3;display:grid;grid-template-columns:1fr 1fr auto;gap:12px;margin-top:20px}.execution-login label span{display:block;font-size:10px;color:#637169;margin-bottom:6px}.execution-login input{width:100%;height:40px;border:1px solid #dce4de;border-radius:8px;padding:0 11px;outline:none}.execution-primary,.report-button,.driver-task button{border:0;border-radius:8px;padding:0 15px;background:#14844d;color:#fff;display:flex;align-items:center;justify-content:center;gap:7px;font-weight:700;cursor:pointer;min-height:40px}.execution-primary:disabled,.driver-task button:disabled{opacity:.6}.demo-account{grid-column:1/3;margin:3px 0 0;color:#8a968f;font-size:10px}.execution-message{padding:10px 13px;border-radius:8px;font-size:11px}.execution-message.success{color:#157444;background:#eaf7ef}.execution-message.error{color:#b33e39;background:#fff0ee}.execution-message.info{color:#48675a;background:#edf4f0}.execution-login .execution-message{grid-column:1/3}.execution-toolbar{height:48px;padding:0 15px;background:#103f2a;color:#fff;border-radius:10px;display:flex;align-items:center;justify-content:space-between}.execution-toolbar>div,.execution-toolbar button{display:flex;align-items:center;gap:8px}.execution-toolbar b{font-size:9px;background:#f2b43f;color:#173a29;padding:3px 7px;border-radius:9px}.execution-toolbar button{border:0;background:transparent;color:#bcd2c6;cursor:pointer}.execution-hero{padding:20px 22px;background:linear-gradient(115deg,#0d4c31,#176f46);color:#fff;border-radius:13px;display:grid;grid-template-columns:1fr auto auto;gap:32px;align-items:center}.execution-hero p{margin:0 0 6px;color:#a9cdbb;font-size:10px}.execution-hero h2{margin:0 0 5px;font-size:23px}.execution-hero>div>span{color:#bad0c5;font-size:10px}.hero-metrics{display:flex;gap:30px}.hero-metrics p{min-width:72px}.hero-metrics span,.hero-metrics b{display:block}.hero-metrics b{font-size:20px;color:#fff;margin-top:5px}.hero-metrics small{font-size:9px;margin-left:3px}.execution-hero .execution-primary,.execution-hero .report-button{background:#f2b43f;color:#153a29}.execution-flow{display:grid;grid-template-columns:repeat(6,1fr);padding:17px 20px;background:#fff;border:1px solid #e2e8e3;border-radius:12px}.flow-step{position:relative;display:flex;align-items:center;gap:8px;color:#9aa59f}.flow-step>span{width:28px;height:28px;display:grid;place-items:center;border-radius:50%;background:#edf1ee}.flow-step p{margin:0}.flow-step strong,.flow-step small{display:block}.flow-step strong{font-size:10px}.flow-step small{font-size:8px;margin-top:3px}.flow-step>svg{position:absolute;right:8px;color:#cad3cd}.flow-step.done{color:#17834f}.flow-step.done>span{color:#fff;background:#17834f}.flow-step.current strong{color:#16452e}.execution-grid{display:grid;grid-template-columns:minmax(650px,1fr) 285px;gap:14px}.execution-list,.audit-card{background:#fff;border:1px solid #e2e8e3;border-radius:12px}.execution-list{padding:17px}.execution-list header{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:12px;border-bottom:1px solid #e8ece9}.execution-list h2{margin:0;font-size:15px}.execution-list header p{margin:4px 0 0;color:#849087;font-size:9px}.execution-list header>span{font-size:9px;color:#17834f;background:#eaf6ef;padding:5px 8px;border-radius:7px}.assignment-row{display:grid;grid-template-columns:38px 1fr 100px 72px;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid #edf0ee}.truck-icon{width:34px;height:34px;display:grid;place-items:center;color:#16834f;background:#eaf6ef;border-radius:8px}.assignment-row strong,.assignment-row small{display:block}.assignment-row strong{font-size:11px}.assignment-row small{color:#849087;font-size:8px;margin-top:4px}.assignment-row p{margin:0}.assignment-row p b{font-size:11px}.assignment-status{text-align:center;font-size:9px;padding:5px 7px;border-radius:7px;background:#eef2ef;color:#637169}.assignment-status.accepted,.assignment-status.executing{background:#e9f3ff;color:#2878d0}.assignment-status.completed{background:#e9f6ee;color:#17834f}.audit-card{padding:22px;color:#315143}.audit-card>svg{color:#17834f}.audit-card h3{margin:12px 0 7px}.audit-card p{font-size:10px;line-height:1.7;color:#77857d}.audit-card ul{list-style:none;padding:12px 0 0;margin:14px 0 0;border-top:1px solid #e6ebe7}.audit-card li{display:flex;gap:6px;margin:9px 0;font-size:9px;color:#587064}.audit-card li svg{color:#17834f}.execution-empty{padding:30px;text-align:center;color:#8a968f;font-size:10px}.driver-toolbar{background:#143f5f}.driver-summary{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border:1px solid #e1e7e2;border-radius:12px}.driver-summary>div{padding:17px 22px;border-right:1px solid #e6ebe7}.driver-summary>div:last-child{border:0}.driver-summary span,.driver-summary b{display:block}.driver-summary span{font-size:10px;color:#7b8981}.driver-summary b{font-size:20px;color:#16462f;margin-top:6px}.driver-task-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.driver-task{padding:17px;background:#fff;border:1px solid #e0e7e2;border-top:4px solid #f2b43f;border-radius:12px}.driver-task.accepted{border-top-color:#2878d0}.driver-task.executing{border-top-color:#17834f}.driver-task.completed{border-top-color:#91a199}.driver-task header{display:flex;align-items:center;gap:9px}.driver-task header>span{width:35px;height:35px;display:grid;place-items:center;background:#edf5f0;color:#17834f;border-radius:9px}.driver-task header div{flex:1}.driver-task header strong,.driver-task header small{display:block}.driver-task header strong{font-size:12px}.driver-task header small{font-size:8px;color:#849087;margin-top:4px}.driver-task header>b{font-size:9px;color:#5c6b63}.task-route{display:flex;align-items:center;gap:9px;margin:16px 0;padding:12px;background:#f2f6f3;border-radius:9px;color:#17834f}.task-route p{margin:0}.task-route span,.task-route strong{display:block}.task-route span{font-size:8px;color:#7d8982}.task-route strong{font-size:11px;margin-top:3px}.driver-task dl{display:grid;grid-template-columns:1fr 1fr;margin:0 0 14px}.driver-task dl>div{padding:8px;border-bottom:1px solid #edf0ee}.driver-task dt{font-size:8px;color:#88948d}.driver-task dd{margin:4px 0 0;font-size:10px;font-weight:700}.driver-task button{width:100%}.driver-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.driver-actions button{min-width:0;padding:0 8px}.driver-nav-button{background:#126fa6!important}.task-complete{height:40px;display:flex;align-items:center;justify-content:center;gap:6px;border-radius:8px;color:#17834f;background:#eaf6ef;font-size:10px}.task-stops{margin:0 0 14px;padding:10px 12px;background:#fbfcfb;border:1px solid #e6ece8;border-radius:8px}.task-stops-heading{display:flex;justify-content:space-between;align-items:center;color:#6d7c73;font-size:9px}.task-stops-heading small{color:#96a29b}.task-stops ol{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px;list-style:none;padding:8px 0 0;margin:0}.task-stops li{display:flex;align-items:center;gap:5px;min-width:0;color:#7f8c84;font-size:8px}.task-stops li>span{width:17px;height:17px;display:grid;place-items:center;flex:none;border-radius:50%;background:#eef2ef;color:#6e7c74;font-size:8px}.task-stops li b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500}.task-stops li.current{color:#126fa6}.task-stops li.current>span{background:#d9edfb;color:#126fa6;font-weight:700}.task-stops li.completed{color:#17834f}.task-stops li.completed>span{background:#dff2e7;color:#17834f}.driver-empty{grid-column:1/4;background:#fff;border-radius:12px}
</style>
