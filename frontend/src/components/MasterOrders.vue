<script setup lang="ts">
import {
  AlertCircle, Check, ChevronLeft, ChevronRight, Clock3, LoaderCircle, Pencil,
  Plus, RefreshCw, Search, ShieldCheck, Trash2, UploadCloud, X,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  createMasterOrder, deleteMasterOrder, getMasterNodes, getMasterOrders, updateMasterOrder,
} from '../services/api'
import type {
  MasterNode, MasterOrder, MasterOrderCreate, MasterOrderInput, MasterOrderStatus, MasterPriority,
} from '../types/logistics'
import ConfirmDialog from './ConfirmDialog.vue'

const emit = defineEmits<{ changed: [] }>()
const router = useRouter()
const items = ref<MasterOrder[]>([])
const nodes = ref<MasterNode[]>([])
const total = ref(0)
const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const drawerOpen = ref(false)
const editing = ref<MasterOrder>()
const deleteTarget = ref<MasterOrder>()
const page = ref(1)
const pageSize = 10
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const filters = reactive({ search: '', status: '', priority: '', cold_chain: '' })
const applied = reactive({ ...filters })
const form = reactive({
  id: '',
  node_id: '',
  cargo_name: '',
  customer_name: '',
  customer_phone: '',
  delivery_address: '',
  weight_kg: 500,
  window_start: '08:00',
  window_end: '12:00',
  service_minutes: 8,
  cold_chain: false,
  priority: 'normal' as MasterPriority,
  flow_direction: 'downward' as 'upward' | 'downward',
  cargo_category: 'industrial' as 'agricultural' | 'industrial',
  origin_node_id: '',
  destination_node_id: '',
  status: 'pending' as MasterOrderStatus,
})
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const canSave = computed(() =>
  form.id.trim().length >= 3
  && form.node_id
  && form.cargo_name.trim()
  && form.customer_name.trim()
  && form.weight_kg > 0
  && timeToMinute(form.window_end) > timeToMinute(form.window_start),
)
const statusNames: Record<MasterOrderStatus, string> = {
  pending: '待调度',
  planned: '已规划',
  completed: '已完成',
  cancelled: '已取消',
}
const priorityNames: Record<MasterPriority, string> = { normal: '普通', urgent: '紧急' }
const flowDirectionNames = { upward: '农产品上行', downward: '工业品下行' }
const cargoCategoryNames = { agricultural: '农产品', industrial: '工业品' }

function timeToMinute(value: string) {
  const [hour, minute] = value.split(':').map(Number)
  return hour * 60 + minute
}
function minuteToTime(value: number) {
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`
}
function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}
function newOrderId() {
  const now = new Date()
  const stamp = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0'),
  ].join('')
  return `QD${stamp}`
}
function queryString() {
  const params = new URLSearchParams({
    limit: String(pageSize),
    offset: String((page.value - 1) * pageSize),
  })
  if (applied.search) params.set('search', applied.search)
  if (applied.status) params.set('status', applied.status)
  if (applied.priority) params.set('priority', applied.priority)
  if (applied.cold_chain) params.set('cold_chain', applied.cold_chain)
  return params.toString()
}
async function load() {
  loading.value = true
  try {
    const result = await getMasterOrders(queryString())
    items.value = result.items
    total.value = result.total
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '订单读取失败' }
  } finally {
    loading.value = false
  }
}
async function loadNodes() {
  const result = await getMasterNodes('active=true&limit=100')
  nodes.value = result.items
}
function query() {
  Object.assign(applied, filters)
  page.value = 1
  load()
}
function resetFilters() {
  Object.assign(filters, { search: '', status: '', priority: '', cold_chain: '' })
  query()
}
function resetForm() {
  Object.assign(form, {
    id: newOrderId(),
    node_id: nodes.value[0]?.id ?? '',
    cargo_name: '黄花菜',
    customer_name: '',
    customer_phone: '',
    delivery_address: '',
    weight_kg: 500,
    window_start: '08:00',
    window_end: '12:00',
    service_minutes: 8,
    cold_chain: false,
    priority: 'normal',
    flow_direction: 'downward',
    cargo_category: 'industrial',
    origin_node_id: '',
    destination_node_id: '',
    status: 'pending',
  })
}
async function openCreate() {
  editing.value = undefined
  if (!nodes.value.length) await loadNodes()
  resetForm()
  drawerOpen.value = true
}
async function openEdit(item: MasterOrder) {
  editing.value = item
  if (!nodes.value.length) await loadNodes()
  Object.assign(form, {
    ...item,
    customer_phone: item.customer_phone ?? '',
    delivery_address: item.delivery_address ?? '',
    window_start: minuteToTime(item.window_start),
    window_end: minuteToTime(item.window_end),
  })
  drawerOpen.value = true
}
function payload(): MasterOrderInput {
  return {
    node_id: form.node_id,
    cargo_name: form.cargo_name.trim(),
    customer_name: form.customer_name.trim(),
    customer_phone: form.customer_phone.trim() || undefined,
    delivery_address: form.delivery_address.trim() || undefined,
    weight_kg: form.weight_kg,
    window_start: timeToMinute(form.window_start),
    window_end: timeToMinute(form.window_end),
    service_minutes: form.service_minutes,
    cold_chain: form.cold_chain,
    priority: form.priority,
    flow_direction: form.flow_direction,
    cargo_category: form.cargo_category,
    origin_node_id: form.origin_node_id || undefined,
    destination_node_id: form.destination_node_id || undefined,
    status: form.status,
  }
}
async function save() {
  if (!canSave.value || saving.value) return
  saving.value = true
  try {
    if (editing.value) {
      await updateMasterOrder(editing.value.id, payload())
      notice.value = { kind: 'success', text: `订单 ${editing.value.id} 已更新` }
    } else {
      await createMasterOrder({ id: form.id.trim(), ...payload() } satisfies MasterOrderCreate)
      notice.value = { kind: 'success', text: `订单 ${form.id.trim()} 已创建` }
    }
    drawerOpen.value = false
    await load()
    emit('changed')
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '订单保存失败' }
  } finally {
    saving.value = false
  }
}
async function remove() {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    const id = deleteTarget.value.id
    await deleteMasterOrder(id)
    notice.value = { kind: 'success', text: `订单 ${id} 已删除` }
    deleteTarget.value = undefined
    await load()
    emit('changed')
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '订单删除失败' }
    deleteTarget.value = undefined
  } finally {
    deleting.value = false
  }
}
async function changePage(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next))
  await load()
}

onMounted(() => Promise.all([load(), loadNodes()]))
</script>

<template>
  <div v-if="notice" class="master-notice" :class="notice.kind">
    <Check v-if="notice.kind === 'success'" :size="17" /><AlertCircle v-else :size="17" />
    <span>{{ notice.text }}</span><button @click="notice = undefined"><X :size="15" /></button>
  </div>

  <article class="master-surface">
    <div class="master-command">
      <form class="master-filters" @submit.prevent="query">
        <label class="master-search"><Search :size="17" /><input v-model.trim="filters.search" placeholder="搜索订单编号、货物或客户" /></label>
        <select v-model="filters.status"><option value="">全部状态</option><option v-for="(label,key) in statusNames" :key="key" :value="key">{{ label }}</option></select>
        <select v-model="filters.priority"><option value="">全部优先级</option><option value="urgent">紧急</option><option value="normal">普通</option></select>
        <select v-model="filters.cold_chain"><option value="">全部冷链要求</option><option value="true">需要冷链</option><option value="false">普通运输</option></select>
        <button class="master-filter-button">查询</button>
        <button class="master-reset-button" type="button" @click="resetFilters"><RefreshCw :size="15" />重置</button>
      </form>
      <div class="master-actions">
        <button class="master-secondary" @click="router.push('/master-data/quality?import=1')"><UploadCloud :size="16" />批量导入</button>
        <button class="master-primary" @click="openCreate"><Plus :size="17" />新建订单</button>
      </div>
    </div>

    <div class="master-table-scroll">
      <div class="master-row master-head order"><span>订单编号</span><span>货物 / 客户</span><span>服务网点</span><span>重量</span><span>时间窗</span><span>冷链</span><span>优先级</span><span>状态</span><span>更新时间</span><span>操作</span></div>
      <div v-for="item in items" :key="item.id" class="master-row order">
        <code>{{ item.id }}</code>
        <div class="master-main-cell"><strong>{{ item.cargo_name }}</strong><span>{{ item.customer_name }}</span><small class="order-flow-label">{{ flowDirectionNames[item.flow_direction] }} · {{ cargoCategoryNames[item.cargo_category] }}</small></div>
        <span>{{ item.node_name }}</span>
        <strong>{{ item.weight_kg.toLocaleString() }} kg</strong>
        <span>{{ minuteToTime(item.window_start) }}–{{ minuteToTime(item.window_end) }}</span>
        <span>{{ item.cold_chain ? '❄ 需要' : '—' }}</span>
        <span class="master-tag" :class="{ urgent: item.priority === 'urgent' }">{{ priorityNames[item.priority] }}</span>
        <span class="master-state" :class="{ blue: item.status === 'planned', red: item.status === 'cancelled', gray: item.status === 'completed' }"><i />{{ statusNames[item.status] }}</span>
        <span>{{ formatTime(item.updated_at) }}</span>
        <div class="master-row-actions"><button @click="openEdit(item)"><Pencil :size="14" />编辑</button><button class="danger" @click="deleteTarget = item"><Trash2 :size="14" />删除</button></div>
      </div>
      <div v-if="loading" class="master-empty"><LoaderCircle class="master-spin" :size="25" />正在读取订单</div>
      <div v-else-if="!items.length" class="master-empty"><Clock3 :size="28" /><strong>没有符合条件的订单</strong><span>调整筛选条件或新建订单。</span></div>
    </div>
    <footer class="master-footer"><span>共 {{ total }} 条</span><div class="master-pager"><button :disabled="page <= 1" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button><b>{{ page }}</b><button :disabled="page >= pageCount" @click="changePage(page + 1)"><ChevronRight :size="16" /></button><span>{{ pageSize }} 条/页</span></div></footer>
  </article>

  <Teleport to="body">
    <div v-if="drawerOpen" class="master-drawer-layer" @mousedown.self="drawerOpen = false">
      <aside class="master-drawer" role="dialog" aria-modal="true">
        <header><div><small>{{ editing ? '更新订单业务信息' : '创建新的配送需求' }}</small><h2>{{ editing ? '编辑订单' : '新建订单' }}</h2></div><button class="master-close" @click="drawerOpen = false"><X :size="21" /></button></header>
        <form id="master-order-form" @submit.prevent="save">
          <div class="master-form-grid">
            <label class="span-2"><span>订单编号 <b>*</b></span><input v-model.trim="form.id" :disabled="Boolean(editing)" required maxlength="32" /><small>创建后不可修改，用于调度与审计追踪。</small></label>
            <label><span>货物名称 <b>*</b></span><input v-model.trim="form.cargo_name" required maxlength="120" /></label>
            <label><span>客户名称 <b>*</b></span><input v-model.trim="form.customer_name" required maxlength="120" /></label>
            <label><span>联系电话</span><input v-model.trim="form.customer_phone" maxlength="32" placeholder="选填" /></label>
            <label><span>服务网点 <b>*</b></span><select v-model="form.node_id" required><option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.name }}</option></select></label>
            <label><span>物流方向 <b>*</b></span><select v-model="form.flow_direction"><option value="upward">农产品上行</option><option value="downward">工业品下行</option></select></label>
            <label><span>货物类别 <b>*</b></span><select v-model="form.cargo_category"><option value="agricultural">农产品</option><option value="industrial">工业品</option></select></label>
            <label class="span-2"><span>配送地址</span><textarea v-model.trim="form.delivery_address" maxlength="300" placeholder="客户或交付点详细地址" /></label>
            <label><span>重量（kg） <b>*</b></span><input v-model.number="form.weight_kg" type="number" min="1" max="100000" required /></label>
            <label><span>服务时长（分钟）</span><input v-model.number="form.service_minutes" type="number" min="0" max="240" /></label>
            <label><span>时间窗开始 <b>*</b></span><input v-model="form.window_start" type="time" required /></label>
            <label><span>时间窗结束 <b>*</b></span><input v-model="form.window_end" type="time" required /></label>
            <label><span>优先级 <b>*</b></span><select v-model="form.priority"><option value="normal">普通</option><option value="urgent">紧急</option></select></label>
            <label><span>订单状态 <b>*</b></span><select v-model="form.status"><option v-for="(label,key) in statusNames" :key="key" :value="key">{{ label }}</option></select></label>
          </div>
          <label class="master-switch"><div><strong>冷链要求</strong><small>启用后只会分配具备冷链能力的车辆。</small></div><span><input v-model="form.cold_chain" type="checkbox" />需要冷链</span></label>
          <div class="master-quality"><ShieldCheck :size="19" /><p><b>数据质量提示</b><span>系统会校验网点状态、重量和时间窗，未通过校验的数据不会进入调度求解。</span></p></div>
        </form>
        <footer><button class="master-cancel" :disabled="saving" @click="drawerOpen = false">取消</button><button class="master-save" form="master-order-form" :disabled="saving || !canSave"><LoaderCircle v-if="saving" class="master-spin" :size="17" /><Check v-else :size="17" />{{ editing ? '保存修改' : '保存订单' }}</button></footer>
      </aside>
    </div>
  </Teleport>

  <ConfirmDialog
    :open="Boolean(deleteTarget)"
    title="删除订单"
    :message="`确认删除订单 ${deleteTarget?.id ?? ''}？只有待调度或已取消订单允许删除，操作会写入审计日志。`"
    :busy="deleting"
    @cancel="deleteTarget = undefined"
    @confirm="remove"
  />
</template>
