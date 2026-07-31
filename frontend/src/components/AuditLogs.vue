<script setup lang="ts">
import { AlertCircle, CalendarDays, Check, ChevronLeft, ChevronRight, Download, Eye, FileClock, LoaderCircle, RefreshCw, Search, ShieldCheck, X } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { downloadAuditLogs, getAuditLogs } from '../services/api'
import type { AuditLog } from '../types/logistics'

const logs = ref<AuditLog[]>([])
const total = ref(0)
const loading = ref(true)
const exporting = ref(false)
const selected = ref<AuditLog>()
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const page = ref(1)
const pageSize = 10
const filters = reactive({ days: '7', category: '', outcome: '', actor: '', search: '' })
const applied = reactive({ ...filters })
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const categoryNames: Record<string, string> = {
  authentication: '身份认证',
  ai_configuration: 'AI 配置',
  user_management: '用户管理',
  master_data: '基础数据',
}
const actionNames: Record<string, string> = {
  login: '用户登录',
  logout: '退出登录',
  create: '新建连接',
  update: '更新连接',
  test: '测试连接',
  activate: '启用连接',
  disable: '停用连接',
  create_user: '新建用户',
  update_user: '更新用户',
  reset_password: '重置密码',
  create_order: '新建订单',
  update_order: '更新订单',
  delete_order: '删除订单',
  create_vehicle: '新建车辆',
  update_vehicle: '更新车辆',
  delete_vehicle: '删除车辆',
  create_node: '新建网点',
  update_node: '更新网点',
  delete_node: '删除网点',
  preview_order_import: '预检订单文件',
  commit_order_import: '确认订单入库',
  update_quality_rule: '更新质量规则',
  publish_scenario: '发布调度场景',
}
const outcomeNames = { success: '成功', failed: '失败', blocked: '已拦截' }

function queryString(includePaging = true) {
  const params = new URLSearchParams({ days: applied.days })
  if (applied.category) params.set('category', applied.category)
  if (applied.outcome) params.set('outcome', applied.outcome)
  if (applied.actor) params.set('actor', applied.actor)
  if (applied.search) params.set('search', applied.search)
  if (includePaging) {
    params.set('limit', String(pageSize))
    params.set('offset', String((page.value - 1) * pageSize))
  }
  return params.toString()
}
function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).format(new Date(value))
}
function localDateStamp() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
async function load() {
  loading.value = true
  try {
    const result = await getAuditLogs(queryString())
    logs.value = result.items
    total.value = result.total
    if (selected.value) selected.value = result.items.find(item => item.id === selected.value?.id)
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '审计日志加载失败' }
  } finally { loading.value = false }
}
function query() {
  Object.assign(applied, filters)
  page.value = 1
  selected.value = undefined
  load()
}
function reset() {
  Object.assign(filters, { days: '7', category: '', outcome: '', actor: '', search: '' })
  query()
}
async function changePage(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next))
  selected.value = undefined
  await load()
}
async function exportRecords() {
  exporting.value = true
  try {
    const blob = await downloadAuditLogs(queryString(false))
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `audit-logs-${localDateStamp()}.csv`
    link.click()
    URL.revokeObjectURL(url)
    notice.value = { kind: 'success', text: '审计日志已导出为 CSV' }
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '导出失败' }
  } finally { exporting.value = false }
}

onMounted(load)
</script>

<template>
  <section class="audit-page">
    <div class="page-toolbar">
      <div><h2>审计日志</h2><p>追踪身份验证、权限变更与关键配置操作</p></div>
      <button class="export-button" :disabled="exporting" @click="exportRecords"><LoaderCircle v-if="exporting" class="spin" :size="17" /><Download v-else :size="17" />导出记录</button>
    </div>
    <div v-if="notice" class="notice" :class="notice.kind"><Check v-if="notice.kind === 'success'" :size="17" /><AlertCircle v-else :size="17" /><span>{{ notice.text }}</span><button @click="notice = undefined"><X :size="15" /></button></div>

    <div class="audit-workspace" :class="{ detailed: selected }">
      <article class="audit-table">
        <form class="filters" @submit.prevent="query">
          <label><span>时间范围</span><div class="select-icon"><CalendarDays :size="16" /><select v-model="filters.days"><option value="1">最近 24 小时</option><option value="7">最近 7 天</option><option value="30">最近 30 天</option><option value="90">最近 90 天</option></select></div></label>
          <label><span>分类</span><select v-model="filters.category"><option value="">全部分类</option><option value="authentication">身份认证</option><option value="ai_configuration">AI 配置</option><option value="user_management">用户管理</option><option value="master_data">基础数据</option></select></label>
          <label><span>结果</span><select v-model="filters.outcome"><option value="">全部结果</option><option value="success">成功</option><option value="failed">失败</option><option value="blocked">已拦截</option></select></label>
          <label><span>操作者</span><input v-model.trim="filters.actor" placeholder="输入操作者" /></label>
          <label><span>资源或动作</span><div class="search-field"><Search :size="16" /><input v-model.trim="filters.search" placeholder="搜索资源或动作" /></div></label>
          <div class="filter-actions"><button class="query-button">查询</button><button class="reset-button" type="button" @click="reset"><RefreshCw :size="15" />重置</button></div>
        </form>
        <div class="table-scroll">
          <div class="audit-row audit-head"><span>时间</span><span>分类</span><span>动作</span><span>操作者</span><span>资源</span><span>来源 IP</span><span>结果</span><span>详情</span></div>
          <button v-for="item in logs" :key="item.id" class="audit-row" :class="{ selected: selected?.id === item.id }" @click="selected = item">
            <span>{{ formatTime(item.created_at) }}</span>
            <span>{{ categoryNames[item.category] ?? item.category }}</span>
            <strong>{{ actionNames[item.action] ?? item.action }}</strong>
            <code>{{ item.actor_username ?? '系统' }}</code>
            <span>{{ item.resource_id ?? item.resource_type ?? '管理后台' }}</span>
            <code>{{ item.ip_address ?? '—' }}</code>
            <span class="outcome" :class="item.outcome"><i />{{ outcomeNames[item.outcome] }}</span>
            <span class="view-action"><Eye :size="14" />查看</span>
          </button>
          <div v-if="loading" class="empty"><LoaderCircle class="spin" :size="25" />正在读取审计记录</div>
          <div v-else-if="!logs.length" class="empty"><FileClock :size="28" /><strong>没有符合条件的审计记录</strong><span>调整筛选条件后重试。</span></div>
        </div>
        <footer><span>共 {{ total }} 条</span><div><button :disabled="page <= 1" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button><b>{{ page }}</b><button :disabled="page >= pageCount" @click="changePage(page + 1)"><ChevronRight :size="16" /></button><small>{{ pageSize }} 条/页</small></div></footer>
      </article>

      <aside v-if="selected" class="audit-detail">
        <header><h3>审计详情</h3><button @click="selected = undefined"><X :size="20" /></button></header>
        <dl>
          <div><dt>事件编号</dt><dd>evt_{{ selected.id.toString().padStart(8,'0') }}</dd></div>
          <div><dt>发生时间</dt><dd>{{ formatTime(selected.created_at) }}</dd></div>
          <div><dt>操作者</dt><dd>{{ selected.actor_username ?? '系统' }}</dd></div>
          <div><dt>来源 IP</dt><dd>{{ selected.ip_address ?? '—' }}</dd></div>
          <div><dt>User-Agent</dt><dd>{{ selected.user_agent ?? '—' }}</dd></div>
          <div><dt>资源</dt><dd>{{ selected.resource_type ?? '管理后台' }} / {{ selected.resource_id ?? '—' }}</dd></div>
          <div><dt>结果</dt><dd><span class="outcome" :class="selected.outcome"><i />{{ outcomeNames[selected.outcome] }}</span></dd></div>
        </dl>
        <div class="detail-json"><h4>结构化详情</h4><pre>{{ JSON.stringify(selected.detail, null, 2) }}</pre></div>
        <div class="security-note"><ShieldCheck :size="18" /><p><b>敏感字段已自动脱敏</b><span>密码、令牌、密钥和认证凭据不会出现在审计详情中。</span></p></div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.audit-page{display:flex;flex-direction:column;gap:18px;color:#22372d}.page-toolbar{display:flex;align-items:flex-start;justify-content:space-between}.page-toolbar h2{margin:0;font-size:25px}.page-toolbar p{margin:8px 0 0;color:#748178;font-size:13px}.export-button{height:40px;display:flex;align-items:center;gap:7px;padding:0 14px;border:1px solid #8bb9a1;border-radius:7px;background:#fff;color:#116c47;font-weight:750;cursor:pointer}.notice{display:flex;gap:8px;align-items:center;padding:11px 13px;border-radius:8px;font-size:13px}.notice.success{background:#edf7f1;border:1px solid #cce4d5;color:#136c46}.notice.error{background:#fff1f0;border:1px solid #edcecb;color:#a53e38}.notice button{margin-left:auto;border:0;background:transparent;color:inherit}
.audit-workspace{display:grid;grid-template-columns:minmax(850px,1fr);gap:10px}.audit-workspace.detailed{grid-template-columns:minmax(730px,1fr) 380px}.audit-table,.audit-detail{overflow:hidden;border:1px solid #dfe5e1;border-radius:9px;background:#fff}.filters{display:grid;grid-template-columns:135px 135px 135px 145px minmax(150px,1fr) 128px;align-items:end;gap:8px;padding:15px 16px;border-bottom:1px solid #e4e9e6}.filters label{display:flex;flex-direction:column;gap:6px}.filters label>span{color:#53645b;font-size:11px;font-weight:750}.filters input,.filters select{width:100%;height:39px;border:1px solid #d5ddd8;border-radius:6px;padding:0 10px;background:#fff;color:#2d4036;font:inherit;font-size:12px;outline:none}.filters input:focus,.filters select:focus{border-color:#18784f;box-shadow:0 0 0 3px rgba(24,120,79,.1)}.select-icon,.search-field{position:relative}.select-icon svg,.search-field svg{position:absolute;left:10px;top:12px;color:#66766d}.select-icon select,.search-field input{padding-left:33px}.filter-actions{display:flex;gap:6px}.filter-actions button{height:39px;padding:0 11px;border-radius:6px;font-weight:750;white-space:nowrap;cursor:pointer}.query-button{border:0;background:#0f6a45;color:#fff}.reset-button{display:flex;align-items:center;gap:5px;border:1px solid #d3dcd6;background:#fff;color:#53665b}
.table-scroll{overflow-x:auto}.audit-row{width:100%;min-width:930px;display:grid;grid-template-columns:1.35fr .8fr .9fr .75fr 1fr .95fr .7fr .55fr;align-items:center;gap:12px;min-height:67px;padding:0 16px;border:0;border-bottom:1px solid #e8ece9;background:#fff;color:#31463a;text-align:left;font:inherit;font-size:12px;cursor:pointer}.audit-row:hover:not(.audit-head),.audit-row.selected{background:#f0f7f3}.audit-head{min-height:42px;background:#f7f9f7;color:#6c7971;font-weight:800;cursor:default}.audit-row code{font-size:11px;color:#41564b}.outcome{display:flex;align-items:center;gap:6px}.outcome i{width:7px;height:7px;border-radius:50%;background:#1c995f}.outcome.failed i,.outcome.blocked i{background:#e2463f}.outcome.failed,.outcome.blocked{color:#b9403a}.view-action{display:flex;align-items:center;gap:4px;color:#146e49;font-weight:750}.empty{min-height:260px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:#7b8a82}.empty span{font-size:12px}.audit-table>footer{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;color:#748179;font-size:12px}.audit-table footer div{display:flex;align-items:center;gap:7px}.audit-table footer button,.audit-table footer b{width:32px;height:32px;display:grid;place-items:center;border:1px solid #d7dfda;border-radius:6px;background:#fff;color:#52645a}.audit-table footer b{border-color:#18744d;color:#147149}.audit-table footer small{margin-left:5px}
.audit-detail{align-self:start}.audit-detail header{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;border-bottom:1px solid #e2e7e4}.audit-detail h3{margin:0;font-size:15px}.audit-detail header button{border:0;background:transparent;color:#607067;cursor:pointer}.audit-detail dl{margin:0;padding:12px 18px}.audit-detail dl div{display:grid;grid-template-columns:95px 1fr;gap:10px;padding:9px 0}.audit-detail dt{color:#6e7d74;font-size:11px}.audit-detail dd{margin:0;color:#34483d;font-size:11px;line-height:1.55;word-break:break-word}.detail-json{padding:0 18px}.detail-json h4{margin:4px 0 8px;font-size:12px}.detail-json pre{max-height:210px;overflow:auto;margin:0;padding:12px;border:1px solid #dde4df;border-radius:7px;background:#f8faf8;color:#294a39;font:11px/1.65 Consolas,monospace;white-space:pre-wrap}.security-note{display:flex;gap:9px;margin:16px 18px 18px;padding:12px;border:1px solid #cce4d5;border-radius:7px;background:#eef8f2;color:#166b46}.security-note p{margin:0}.security-note b,.security-note span{display:block}.security-note b{font-size:11px}.security-note span{margin-top:4px;color:#547466;font-size:10px;line-height:1.5}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1300px){.audit-workspace.detailed{grid-template-columns:1fr}.audit-detail{width:100%}.filters{grid-template-columns:repeat(3,1fr)}.filter-actions{justify-content:flex-end}}@media(max-width:760px){.filters{grid-template-columns:1fr}.page-toolbar{flex-direction:column;gap:15px}.export-button{width:100%;justify-content:center}}
</style>
