<script setup lang="ts">
import {
  AlertCircle, Check, ChevronLeft, ChevronRight, LoaderCircle, MapPinned, Pencil,
  Plus, RefreshCw, Search, ShieldCheck, Trash2, X,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createMasterNode, deleteMasterNode, getMasterNodes, updateMasterNode,
} from '../services/api'
import type {
  MasterNode, MasterNodeCreate, MasterNodeInput, MasterNodeKind,
} from '../types/logistics'
import ConfirmDialog from './ConfirmDialog.vue'

const emit = defineEmits<{ changed: [] }>()
const items = ref<MasterNode[]>([])
const total = ref(0)
const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const drawerOpen = ref(false)
const editing = ref<MasterNode>()
const deleteTarget = ref<MasterNode>()
const page = ref(1)
const pageSize = 10
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const filters = reactive({ search: '', kind: '', active: '' })
const applied = reactive({ ...filters })
const form = reactive({
  id: '',
  name: '',
  longitude: 112.11,
  latitude: 26.79,
  kind: 'town' as MasterNodeKind,
  address: '',
  contact_name: '',
  contact_phone: '',
  service_radius_km: 15,
  is_active: true,
})
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const canSave = computed(() =>
  form.id.trim().length >= 3
  && form.name.trim()
  && form.longitude >= -180 && form.longitude <= 180
  && form.latitude >= -90 && form.latitude <= 90
  && form.service_radius_km > 0,
)
const kindNames: Record<MasterNodeKind, string> = {
  depot: '配送中心',
  town: '乡镇服务站',
  village: '村级服务点',
  processor: '加工企业',
}

function newNodeId() {
  return `N-${Date.now().toString().slice(-8)}`
}
function queryString() {
  const params = new URLSearchParams({
    limit: String(pageSize),
    offset: String((page.value - 1) * pageSize),
  })
  if (applied.search) params.set('search', applied.search)
  if (applied.kind) params.set('kind', applied.kind)
  if (applied.active) params.set('active', applied.active)
  return params.toString()
}
async function load() {
  loading.value = true
  try {
    const result = await getMasterNodes(queryString())
    items.value = result.items
    total.value = result.total
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '网点读取失败' }
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
  Object.assign(filters, { search: '', kind: '', active: '' })
  query()
}
function resetForm() {
  Object.assign(form, {
    id: newNodeId(),
    name: '',
    longitude: 112.11,
    latitude: 26.79,
    kind: 'town',
    address: '',
    contact_name: '',
    contact_phone: '',
    service_radius_km: 15,
    is_active: true,
  })
}
function openCreate() {
  editing.value = undefined
  resetForm()
  drawerOpen.value = true
}
function openEdit(item: MasterNode) {
  editing.value = item
  Object.assign(form, {
    ...item,
    address: item.address ?? '',
    contact_name: item.contact_name ?? '',
    contact_phone: item.contact_phone ?? '',
  })
  drawerOpen.value = true
}
function payload(): MasterNodeInput {
  return {
    name: form.name.trim(),
    longitude: form.longitude,
    latitude: form.latitude,
    kind: form.kind,
    address: form.address.trim() || undefined,
    contact_name: form.contact_name.trim() || undefined,
    contact_phone: form.contact_phone.trim() || undefined,
    service_radius_km: form.service_radius_km,
    is_active: form.is_active,
  }
}
async function save() {
  if (!canSave.value || saving.value) return
  saving.value = true
  try {
    if (editing.value) {
      await updateMasterNode(editing.value.id, payload())
      notice.value = { kind: 'success', text: `网点 ${editing.value.name} 已更新` }
    } else {
      await createMasterNode({ id: form.id.trim(), ...payload() } satisfies MasterNodeCreate)
      notice.value = { kind: 'success', text: `网点 ${form.name.trim()} 已创建` }
    }
    drawerOpen.value = false
    await load()
    emit('changed')
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '网点保存失败' }
  } finally {
    saving.value = false
  }
}
async function remove() {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    const label = deleteTarget.value.name
    await deleteMasterNode(deleteTarget.value.id)
    notice.value = { kind: 'success', text: `网点 ${label} 已删除` }
    deleteTarget.value = undefined
    await load()
    emit('changed')
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '网点删除失败' }
    deleteTarget.value = undefined
  } finally {
    deleting.value = false
  }
}
async function changePage(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next))
  await load()
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
        <label class="master-search"><Search :size="17" /><input v-model.trim="filters.search" placeholder="搜索网点编号、名称、地址或联系人" /></label>
        <select v-model="filters.kind"><option value="">全部网点类型</option><option v-for="(label,key) in kindNames" :key="key" :value="key">{{ label }}</option></select>
        <select v-model="filters.active"><option value="">全部状态</option><option value="true">已启用</option><option value="false">已停用</option></select>
        <button class="master-filter-button">查询</button>
        <button class="master-reset-button" type="button" @click="resetFilters"><RefreshCw :size="15" />重置</button>
      </form>
      <div class="master-actions"><button class="master-primary" @click="openCreate"><Plus :size="17" />新建网点</button></div>
    </div>

    <div class="master-table-scroll">
      <div class="master-row master-head node"><span>网点编号</span><span>网点名称</span><span>类型</span><span>地址</span><span>联系人</span><span>服务半径</span><span>状态</span><span>操作</span></div>
      <div v-for="item in items" :key="item.id" class="master-row node">
        <code>{{ item.id }}</code>
        <div class="master-main-cell"><strong>{{ item.name }}</strong><span>{{ item.longitude.toFixed(4) }}, {{ item.latitude.toFixed(4) }}</span></div>
        <span>{{ kindNames[item.kind] }}</span>
        <span>{{ item.address || '未登记' }}</span>
        <div class="master-main-cell"><strong>{{ item.contact_name || '未登记' }}</strong><span>{{ item.contact_phone || '—' }}</span></div>
        <span>{{ item.service_radius_km.toFixed(1) }} km</span>
        <span class="master-state" :class="{ gray: !item.is_active }"><i />{{ item.is_active ? '已启用' : '已停用' }}</span>
        <div class="master-row-actions"><button @click="openEdit(item)"><Pencil :size="14" />编辑</button><button class="danger" @click="deleteTarget = item"><Trash2 :size="14" />删除</button></div>
      </div>
      <div v-if="loading" class="master-empty"><LoaderCircle class="master-spin" :size="25" />正在读取网点</div>
      <div v-else-if="!items.length" class="master-empty"><MapPinned :size="28" /><strong>没有符合条件的网点</strong><span>调整筛选条件或新建网点。</span></div>
    </div>
    <footer class="master-footer"><span>共 {{ total }} 条</span><div class="master-pager"><button :disabled="page <= 1" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button><b>{{ page }}</b><button :disabled="page >= pageCount" @click="changePage(page + 1)"><ChevronRight :size="16" /></button><span>{{ pageSize }} 条/页</span></div></footer>
  </article>

  <Teleport to="body">
    <div v-if="drawerOpen" class="master-drawer-layer" @mousedown.self="drawerOpen = false">
      <aside class="master-drawer" role="dialog" aria-modal="true">
        <header><div><small>{{ editing ? '更新服务范围与联系信息' : '登记新的县域服务节点' }}</small><h2>{{ editing ? '编辑网点' : '新建网点' }}</h2></div><button class="master-close" @click="drawerOpen = false"><X :size="21" /></button></header>
        <form id="master-node-form" @submit.prevent="save">
          <div class="master-form-grid">
            <label><span>网点编号 <b>*</b></span><input v-model.trim="form.id" :disabled="Boolean(editing)" required maxlength="32" /></label>
            <label><span>网点类型 <b>*</b></span><select v-model="form.kind"><option v-for="(label,key) in kindNames" :key="key" :value="key">{{ label }}</option></select></label>
            <label class="span-2"><span>网点名称 <b>*</b></span><input v-model.trim="form.name" required maxlength="200" /></label>
            <label class="span-2"><span>详细地址</span><textarea v-model.trim="form.address" maxlength="300" placeholder="乡镇、街道及门牌信息" /></label>
            <label><span>经度 <b>*</b></span><input v-model.number="form.longitude" type="number" min="-180" max="180" step=".000001" required /></label>
            <label><span>纬度 <b>*</b></span><input v-model.number="form.latitude" type="number" min="-90" max="90" step=".000001" required /></label>
            <label><span>联系人</span><input v-model.trim="form.contact_name" maxlength="120" placeholder="选填" /></label>
            <label><span>联系电话</span><input v-model.trim="form.contact_phone" maxlength="32" placeholder="选填" /></label>
            <label><span>服务半径（km） <b>*</b></span><input v-model.number="form.service_radius_km" type="number" min=".1" max="500" step=".1" required /></label>
          </div>
          <label class="master-switch"><div><strong>网点状态</strong><small>停用后不能承接新订单，但历史订单与审计记录会保留。</small></div><span><input v-model="form.is_active" type="checkbox" />启用</span></label>
          <div class="master-quality"><ShieldCheck :size="19" /><p><b>坐标质量提示</b><span>网点坐标会参与路网距离计算，请使用真实经纬度并确认其位于服务县域内。</span></p></div>
        </form>
        <footer><button class="master-cancel" :disabled="saving" @click="drawerOpen = false">取消</button><button class="master-save" form="master-node-form" :disabled="saving || !canSave"><LoaderCircle v-if="saving" class="master-spin" :size="17" /><MapPinned v-else :size="17" />{{ editing ? '保存修改' : '保存网点' }}</button></footer>
      </aside>
    </div>
  </Teleport>

  <ConfirmDialog
    :open="Boolean(deleteTarget)"
    title="删除服务网点"
    :message="`确认删除网点 ${deleteTarget?.name ?? ''}？被订单引用的网点不能删除，应改为停用。`"
    :busy="deleting"
    @cancel="deleteTarget = undefined"
    @confirm="remove"
  />
</template>
