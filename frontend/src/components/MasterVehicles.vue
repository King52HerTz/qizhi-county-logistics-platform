<script setup lang="ts">
import {
  AlertCircle, Check, ChevronLeft, ChevronRight, LoaderCircle, Pencil, Plus,
  RefreshCw, Search, ShieldCheck, Trash2, Truck, X,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createMasterVehicle, deleteMasterVehicle, getMasterVehicles, updateMasterVehicle,
} from '../services/api'
import type {
  MasterVehicle, MasterVehicleCreate, MasterVehicleInput, MasterVehicleStatus, MasterVehicleType,
} from '../types/logistics'
import ConfirmDialog from './ConfirmDialog.vue'

const emit = defineEmits<{ changed: [] }>()
const items = ref<MasterVehicle[]>([])
const total = ref(0)
const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const drawerOpen = ref(false)
const editing = ref<MasterVehicle>()
const deleteTarget = ref<MasterVehicle>()
const page = ref(1)
const pageSize = 10
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const filters = reactive({ search: '', status: '', cold_chain: '' })
const applied = reactive({ ...filters })
const form = reactive({
  id: '',
  plate: '',
  capacity_kg: 1500,
  cold_chain: false,
  vehicle_type: 'van' as MasterVehicleType,
  driver_name: '',
  driver_phone: '',
  status: 'available' as MasterVehicleStatus,
  cost_per_km: 3.2,
  shift_start: '07:00',
  shift_end: '18:00',
})
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const canSave = computed(() =>
  form.id.trim().length >= 3
  && form.plate.trim().length >= 2
  && form.capacity_kg > 0
  && form.cost_per_km > 0
  && timeToMinute(form.shift_end) > timeToMinute(form.shift_start)
  && (form.vehicle_type !== 'refrigerated' || form.cold_chain),
)
const statusNames: Record<MasterVehicleStatus, string> = {
  available: '可用',
  assigned: '已分配',
  maintenance: '维护中',
  offline: '已停用',
}
const typeNames: Record<MasterVehicleType, string> = {
  van: '厢式车',
  truck: '货车',
  refrigerated: '冷藏车',
}

function timeToMinute(value: string) {
  const [hour, minute] = value.split(':').map(Number)
  return hour * 60 + minute
}
function minuteToTime(value: number) {
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`
}
function newVehicleId() {
  return `V-${Date.now().toString().slice(-8)}`
}
function queryString() {
  const params = new URLSearchParams({
    limit: String(pageSize),
    offset: String((page.value - 1) * pageSize),
  })
  if (applied.search) params.set('search', applied.search)
  if (applied.status) params.set('status', applied.status)
  if (applied.cold_chain) params.set('cold_chain', applied.cold_chain)
  return params.toString()
}
async function load() {
  loading.value = true
  try {
    const result = await getMasterVehicles(queryString())
    items.value = result.items
    total.value = result.total
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '车辆读取失败' }
  } finally {
    loading.value = false
  }
}
function query() {
  Object.assign(applied, filters)
  page.value = 1
  load()
}
function resetFilters() {
  Object.assign(filters, { search: '', status: '', cold_chain: '' })
  query()
}
function resetForm() {
  Object.assign(form, {
    id: newVehicleId(),
    plate: '',
    capacity_kg: 1500,
    cold_chain: false,
    vehicle_type: 'van',
    driver_name: '',
    driver_phone: '',
    status: 'available',
    cost_per_km: 3.2,
    shift_start: '07:00',
    shift_end: '18:00',
  })
}
function openCreate() {
  editing.value = undefined
  resetForm()
  drawerOpen.value = true
}
function openEdit(item: MasterVehicle) {
  editing.value = item
  Object.assign(form, {
    ...item,
    driver_name: item.driver_name ?? '',
    driver_phone: item.driver_phone ?? '',
    shift_start: minuteToTime(item.shift_start),
    shift_end: minuteToTime(item.shift_end),
  })
  drawerOpen.value = true
}
function payload(): MasterVehicleInput {
  return {
    plate: form.plate.trim(),
    capacity_kg: form.capacity_kg,
    cold_chain: form.cold_chain,
    vehicle_type: form.vehicle_type,
    driver_name: form.driver_name.trim() || undefined,
    driver_phone: form.driver_phone.trim() || undefined,
    status: form.status,
    cost_per_km: form.cost_per_km,
    shift_start: timeToMinute(form.shift_start),
    shift_end: timeToMinute(form.shift_end),
  }
}
async function save() {
  if (!canSave.value || saving.value) return
  saving.value = true
  try {
    if (editing.value) {
      await updateMasterVehicle(editing.value.id, payload())
      notice.value = { kind: 'success', text: `车辆 ${editing.value.plate} 已更新` }
    } else {
      await createMasterVehicle({ id: form.id.trim(), ...payload() } satisfies MasterVehicleCreate)
      notice.value = { kind: 'success', text: `车辆 ${form.plate.trim()} 已创建` }
    }
    drawerOpen.value = false
    await load()
    emit('changed')
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '车辆保存失败' }
  } finally {
    saving.value = false
  }
}
async function remove() {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    const label = deleteTarget.value.plate
    await deleteMasterVehicle(deleteTarget.value.id)
    notice.value = { kind: 'success', text: `车辆 ${label} 已删除` }
    deleteTarget.value = undefined
    await load()
    emit('changed')
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '车辆删除失败' }
    deleteTarget.value = undefined
  } finally {
    deleting.value = false
  }
}
async function changePage(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next))
  await load()
}
function selectType() {
  if (form.vehicle_type === 'refrigerated') form.cold_chain = true
}

onMounted(load)
</script>

<template>
  <div v-if="notice" class="master-notice" :class="notice.kind">
    <Check v-if="notice.kind === 'success'" :size="17" /><AlertCircle v-else :size="17" />
    <span>{{ notice.text }}</span><button @click="notice = undefined"><X :size="15" /></button>
  </div>

  <article class="master-surface">
    <div class="master-command">
      <form class="master-filters compact" @submit.prevent="query">
        <label class="master-search"><Search :size="17" /><input v-model.trim="filters.search" placeholder="搜索车辆编号、车牌或驾驶员" /></label>
        <select v-model="filters.status"><option value="">全部状态</option><option v-for="(label,key) in statusNames" :key="key" :value="key">{{ label }}</option></select>
        <select v-model="filters.cold_chain"><option value="">全部冷链能力</option><option value="true">冷链车辆</option><option value="false">普通车辆</option></select>
        <button class="master-filter-button">查询</button>
        <button class="master-reset-button" type="button" @click="resetFilters"><RefreshCw :size="15" />重置</button>
      </form>
      <div class="master-actions"><button class="master-primary" @click="openCreate"><Plus :size="17" />新建车辆</button></div>
    </div>

    <div class="master-table-scroll">
      <div class="master-row master-head vehicle"><span>车辆 / 车牌</span><span>车型</span><span>载重</span><span>冷链</span><span>默认驾驶员</span><span>班次</span><span>公里成本</span><span>状态</span><span>操作</span></div>
      <div v-for="item in items" :key="item.id" class="master-row vehicle">
        <div class="master-main-cell"><strong>{{ item.plate }}</strong><span>{{ item.id }}</span></div>
        <span>{{ typeNames[item.vehicle_type] }}</span>
        <strong>{{ item.capacity_kg.toLocaleString() }} kg</strong>
        <span>{{ item.cold_chain ? '❄ 支持' : '—' }}</span>
        <div class="master-main-cell"><strong>{{ item.driver_name || '未分配' }}</strong><span>{{ item.driver_phone || '—' }}</span></div>
        <span>{{ minuteToTime(item.shift_start) }}–{{ minuteToTime(item.shift_end) }}</span>
        <span>¥{{ item.cost_per_km.toFixed(2) }}</span>
        <span class="master-state" :class="{ blue: item.status === 'assigned', red: item.status === 'maintenance', gray: item.status === 'offline' }"><i />{{ statusNames[item.status] }}</span>
        <div class="master-row-actions"><button @click="openEdit(item)"><Pencil :size="14" />编辑</button><button class="danger" @click="deleteTarget = item"><Trash2 :size="14" />删除</button></div>
      </div>
      <div v-if="loading" class="master-empty"><LoaderCircle class="master-spin" :size="25" />正在读取车辆</div>
      <div v-else-if="!items.length" class="master-empty"><Truck :size="28" /><strong>没有符合条件的车辆</strong><span>调整筛选条件或新建车辆。</span></div>
    </div>
    <footer class="master-footer"><span>共 {{ total }} 条</span><div class="master-pager"><button :disabled="page <= 1" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button><b>{{ page }}</b><button :disabled="page >= pageCount" @click="changePage(page + 1)"><ChevronRight :size="16" /></button><span>{{ pageSize }} 条/页</span></div></footer>
  </article>

  <Teleport to="body">
    <div v-if="drawerOpen" class="master-drawer-layer" @mousedown.self="drawerOpen = false">
      <aside class="master-drawer" role="dialog" aria-modal="true">
        <header><div><small>{{ editing ? '更新车辆与运力信息' : '登记新的运营车辆' }}</small><h2>{{ editing ? '编辑车辆' : '新建车辆' }}</h2></div><button class="master-close" @click="drawerOpen = false"><X :size="21" /></button></header>
        <form id="master-vehicle-form" @submit.prevent="save">
          <div class="master-form-grid">
            <label><span>车辆编号 <b>*</b></span><input v-model.trim="form.id" :disabled="Boolean(editing)" required maxlength="32" /></label>
            <label><span>车牌号 <b>*</b></span><input v-model.trim="form.plate" required maxlength="32" placeholder="例如：湘D·12345" /></label>
            <label><span>车型 <b>*</b></span><select v-model="form.vehicle_type" @change="selectType"><option v-for="(label,key) in typeNames" :key="key" :value="key">{{ label }}</option></select></label>
            <label><span>额定载重（kg） <b>*</b></span><input v-model.number="form.capacity_kg" type="number" min="1" max="100000" required /></label>
            <label><span>默认驾驶员</span><input v-model.trim="form.driver_name" maxlength="120" placeholder="选填" /></label>
            <label><span>联系电话</span><input v-model.trim="form.driver_phone" maxlength="32" placeholder="选填" /></label>
            <label><span>班次开始 <b>*</b></span><input v-model="form.shift_start" type="time" required /></label>
            <label><span>班次结束 <b>*</b></span><input v-model="form.shift_end" type="time" required /></label>
            <label><span>公里成本（元） <b>*</b></span><input v-model.number="form.cost_per_km" type="number" min=".01" max="1000" step=".01" required /></label>
            <label><span>车辆状态 <b>*</b></span><select v-model="form.status"><option v-for="(label,key) in statusNames" :key="key" :value="key">{{ label }}</option></select></label>
          </div>
          <label class="master-switch"><div><strong>冷链能力</strong><small>只有具备冷链能力的车辆可承接冷链订单。</small></div><span><input v-model="form.cold_chain" type="checkbox" :disabled="form.vehicle_type === 'refrigerated'" />支持冷链</span></label>
          <div class="master-quality"><ShieldCheck :size="19" /><p><b>运力状态规则</b><span>只有“可用”状态的车辆会进入调度求解；维护中或停用车辆仍保留历史记录。</span></p></div>
        </form>
        <footer><button class="master-cancel" :disabled="saving" @click="drawerOpen = false">取消</button><button class="master-save" form="master-vehicle-form" :disabled="saving || !canSave"><LoaderCircle v-if="saving" class="master-spin" :size="17" /><Truck v-else :size="17" />{{ editing ? '保存修改' : '保存车辆' }}</button></footer>
      </aside>
    </div>
  </Teleport>

  <ConfirmDialog
    :open="Boolean(deleteTarget)"
    title="删除车辆"
    :message="`确认删除车辆 ${deleteTarget?.plate ?? ''}？已有调度执行记录的车辆不能删除，应改为停用。`"
    :busy="deleting"
    @cancel="deleteTarget = undefined"
    @confirm="remove"
  />
</template>
