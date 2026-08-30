<script setup lang="ts">
import { AlertCircle, Check, ClipboardCheck, Clock3, LoaderCircle, MapPin, Package, RefreshCw, RotateCcw, Send, ShieldCheck, Truck, X } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  cancelOrderRequest,
  createOrderRequest,
  getMyOrderRequests,
  getOrderRequestOptions,
  getOrderRequests,
  reviewOrderRequest,
} from '../services/api'
import type { OrderRequest, OrderRequestNodeOption } from '../types/logistics'

const props = withDefaults(defineProps<{ mode?: 'user' | 'admin' }>(), { mode: 'user' })
const isAdmin = computed(() => props.mode === 'admin')
const requests = ref<OrderRequest[]>([])
const nodeOptions = ref<OrderRequestNodeOption[]>([])
const loading = ref(true)
const submitting = ref(false)
const busyId = ref<number | null>(null)
const notice = ref<{ kind: 'success' | 'error' | 'info'; text: string }>()
const filter = ref('')
const reviewNote = reactive<Record<number, string>>({})

const form = reactive({
  node_id: '',
  cargo_name: '黄花菜',
  customer_name: '',
  customer_phone: '',
  delivery_address: '',
  weight_kg: 500,
  window_start: '08:00',
  window_end: '12:00',
  service_minutes: 8,
  cold_chain: false,
  priority: 'normal' as 'normal' | 'urgent',
})

const statusLabels: Record<OrderRequest['status'], string> = {
  pending_review: '审核中',
  needs_info: '待补充',
  rejected: '未通过',
  converted: '已受理',
  cancelled: '已撤回',
}
const statusHints: Record<OrderRequest['status'], string> = {
  pending_review: '管理员正在核对配送信息',
  needs_info: '请根据审核意见补充信息',
  rejected: '如有疑问请联系平台管理员',
  converted: '已纳入运营调度，后续可跟踪执行状态',
  cancelled: '该申请已从处理队列撤回',
}
const filteredRequests = computed(() => {
  if (!filter.value || !isAdmin.value) return requests.value
  const keyword = filter.value.trim().toLowerCase()
  return requests.value.filter((item) =>
    [item.request_code, item.requester_name, item.customer_name, item.node_name]
      .some(value => value.toLowerCase().includes(keyword)),
  )
})
const pendingCount = computed(() => requests.value.filter(item => item.status === 'pending_review').length)
const convertedCount = computed(() => requests.value.filter(item => item.status === 'converted').length)

function toMinute(value: string) {
  const [hour, minute] = value.split(':').map(Number)
  return hour * 60 + minute
}

function formatTime(value?: string) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function formatWindow(start: number, end: number) {
  const text = (minute: number) => `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`
  return `${text(start)}–${text(end)}`
}

function operationalLabel(status?: string) {
  return ({ pending: '待调度', planned: '已排程', completed: '已送达', cancelled: '已取消' } as Record<string, string>)[status || ''] || '待生成路线'
}

async function load() {
  loading.value = true
  try {
    if (isAdmin.value) {
      requests.value = (await getOrderRequests()).items
    } else {
      const [options, mine] = await Promise.all([getOrderRequestOptions(), getMyOrderRequests()])
      nodeOptions.value = options.items
      requests.value = mine.items
      if (!form.node_id && nodeOptions.value.length) form.node_id = nodeOptions.value[0].id
    }
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '订单申请加载失败' }
  } finally {
    loading.value = false
  }
}

async function submit() {
  const start = toMinute(form.window_start)
  const end = toMinute(form.window_end)
  if (!form.node_id || !form.customer_name.trim() || end <= start) {
    notice.value = { kind: 'error', text: '请填写配送网点、收货人，并确认时间窗有效' }
    return
  }
  submitting.value = true
  notice.value = undefined
  try {
    const created = await createOrderRequest({
      node_id: form.node_id,
      cargo_name: form.cargo_name.trim(),
      customer_name: form.customer_name.trim(),
      customer_phone: form.customer_phone.trim() || undefined,
      delivery_address: form.delivery_address.trim() || undefined,
      weight_kg: Number(form.weight_kg),
      window_start: start,
      window_end: end,
      service_minutes: Number(form.service_minutes),
      cold_chain: form.cold_chain,
      priority: form.priority,
    })
    requests.value = [created, ...requests.value]
    form.customer_name = ''
    form.customer_phone = ''
    form.delivery_address = ''
    notice.value = { kind: 'success', text: `申请 ${created.request_code} 已提交，管理员审核后会进入运营调度。` }
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '订单申请提交失败' }
  } finally {
    submitting.value = false
  }
}

async function review(item: OrderRequest, action: 'approve' | 'reject' | 'needs_info') {
  busyId.value = item.id
  notice.value = undefined
  try {
    const fallback = action === 'approve'
      ? '审核通过，已自动纳入运营调度'
      : action === 'needs_info'
        ? '请补充收货人与配送信息后重新提交'
        : '当前申请不符合运营受理条件'
    const updated = await reviewOrderRequest(item.id, action, reviewNote[item.id]?.trim() || fallback)
    requests.value = requests.value.map(request => request.id === item.id ? updated : request)
    notice.value = {
      kind: 'success',
      text: action === 'approve' ? `${item.request_code} 已转为正式运营订单并生成新场景版本。` : `${item.request_code} 状态已更新为“${statusLabels[updated.status]}”。`,
    }
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '审核操作失败' }
  } finally {
    busyId.value = null
  }
}

async function cancel(item: OrderRequest) {
  busyId.value = item.id
  try {
    const updated = await cancelOrderRequest(item.id)
    requests.value = requests.value.map(request => request.id === item.id ? updated : request)
    notice.value = { kind: 'success', text: `${item.request_code} 已撤回。` }
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '撤回失败' }
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="order-request-center">
    <div v-if="notice" class="order-notice" :class="notice.kind">
      <Check v-if="notice.kind === 'success'" :size="17" />
      <AlertCircle v-else :size="17" />
      <span>{{ notice.text }}</span>
      <button type="button" @click="notice = undefined"><X :size="15" /></button>
    </div>

    <template v-if="!isAdmin">
      <div class="request-overview">
        <article><span class="icon green"><Send :size="18" /></span><div><small>申请总数</small><strong>{{ requests.length }}</strong></div></article>
        <article><span class="icon amber"><Clock3 :size="18" /></span><div><small>处理中</small><strong>{{ requests.filter(item => ['pending_review', 'needs_info'].includes(item.status)).length }}</strong></div></article>
        <article><span class="icon blue"><Truck :size="18" /></span><div><small>已纳入运营</small><strong>{{ convertedCount }}</strong></div></article>
      </div>

      <div class="request-user-grid">
        <article class="request-form-card">
          <div class="section-heading"><div><p class="section-kicker"><Package :size="15" /> 配送需求</p><h2>提交新的订单申请</h2><span>填写收货与配送信息，平台会在审核后自动安排路线。</span></div><ShieldCheck :size="23" /></div>
          <form class="request-form" @submit.prevent="submit">
            <div class="form-grid two">
              <label><span>配送网点 <b>*</b></span><select v-model="form.node_id" required><option value="" disabled>请选择服务网点</option><option v-for="node in nodeOptions" :key="node.id" :value="node.id">{{ node.name }}{{ node.address ? ` · ${node.address}` : '' }}</option></select></label>
              <label><span>货物名称 <b>*</b></span><input v-model.trim="form.cargo_name" maxlength="120" required /></label>
            </div>
            <div class="form-grid two">
              <label><span>收货人 <b>*</b></span><input v-model.trim="form.customer_name" maxlength="120" placeholder="请输入收货人姓名" required /></label>
              <label><span>联系电话</span><input v-model.trim="form.customer_phone" maxlength="32" placeholder="选填" /></label>
            </div>
            <label><span>配送地址</span><input v-model.trim="form.delivery_address" maxlength="300" placeholder="请输入详细地址，便于驾驶员联系" /></label>
            <div class="form-grid three">
              <label><span>重量（kg） <b>*</b></span><input v-model.number="form.weight_kg" min="1" max="100000" type="number" required /></label>
              <label><span>最早送达</span><input v-model="form.window_start" type="time" required /></label>
              <label><span>最晚送达</span><input v-model="form.window_end" type="time" required /></label>
            </div>
            <div class="form-options">
              <label class="check-option"><input v-model="form.cold_chain" type="checkbox" /><span>需要冷链运输</span></label>
              <label><span>优先级</span><select v-model="form.priority"><option value="normal">普通</option><option value="urgent">紧急</option></select></label>
              <label><span>服务时长（分钟）</span><input v-model.number="form.service_minutes" type="number" min="0" max="240" /></label>
            </div>
            <div class="form-foot"><span><MapPin :size="15" />审核通过后自动生成运营订单</span><button class="primary-button" :disabled="submitting || loading"><LoaderCircle v-if="submitting" class="spin" :size="16" /><Send v-else :size="16" />{{ submitting ? '提交中' : '提交申请' }}</button></div>
          </form>
        </article>

        <article class="request-flow-card">
          <div class="section-heading"><div><p class="section-kicker"><ClipboardCheck :size="15" /> 处理流程</p><h2>申请如何进入配送</h2></div></div>
          <ol class="flow-list">
            <li class="active"><i>1</i><div><b>提交需求</b><span>填写网点、货物和时间窗</span></div></li>
            <li><i>2</i><div><b>管理员审核</b><span>核验运力与配送约束</span></div></li>
            <li><i>3</i><div><b>生成运营订单</b><span>自动创建新场景版本</span></div></li>
            <li><i>4</i><div><b>路线执行</b><span>可在下方查看处理状态</span></div></li>
          </ol>
          <div class="flow-note"><ShieldCheck :size="17" /><span>账号只能查看和操作本人提交的申请，平台不会公开其他客户信息。</span></div>
        </article>
      </div>
    </template>

    <article class="request-list-card">
      <div class="list-heading">
        <div><p class="section-kicker"><ClipboardCheck :size="15" /> {{ isAdmin ? '用户需求审核' : '我的申请记录' }}</p><h2>{{ isAdmin ? '待处理的配送需求' : '订单申请与跟踪' }}</h2><span>{{ isAdmin ? `当前有 ${pendingCount} 条申请等待处理，审核通过后会自动进入运营调度。` : '查看每条申请的受理状态、运营订单编号和配送进度。' }}</span></div>
        <div class="list-actions"><label v-if="isAdmin" class="search-box"><MapPin :size="15" /><input v-model.trim="filter" placeholder="搜索申请编号、客户或网点" /></label><button class="ghost-button" type="button" @click="load"><RefreshCw :size="15" />刷新</button></div>
      </div>
      <div v-if="loading" class="request-empty"><LoaderCircle class="spin" :size="25" /><span>正在读取申请记录…</span></div>
      <div v-else-if="!filteredRequests.length" class="request-empty"><Package :size="28" /><strong>{{ isAdmin ? '暂无待处理的用户申请' : '还没有订单申请' }}</strong><span>{{ isAdmin ? '新申请会自动出现在这里。' : '提交一条配送需求后，处理进度会显示在这里。' }}</span></div>
      <div v-else class="request-list">
        <article v-for="item in filteredRequests" :key="item.id" class="request-item">
          <div class="request-item-main">
            <div class="request-code"><span :class="`status-dot ${item.status}`" /><strong>{{ item.request_code }}</strong><small>{{ formatTime(item.created_at) }}</small></div>
            <div class="request-summary"><b>{{ item.cargo_name }} · {{ item.weight_kg }} kg</b><span><MapPin :size="14" />{{ item.node_name }} · {{ formatWindow(item.window_start, item.window_end) }} · {{ item.cold_chain ? '冷链' : '常温' }}</span></div>
            <div v-if="isAdmin" class="request-customer"><span>申请人</span><b>{{ item.requester_name }}</b><span>收货人</span><b>{{ item.customer_name }}</b></div>
          </div>
          <div class="request-item-side">
            <span class="status-pill" :class="item.status">{{ statusLabels[item.status] }}</span>
            <small>{{ item.status === 'converted' ? operationalLabel(item.operational_status) : statusHints[item.status] }}</small>
            <strong v-if="item.operational_order_id" class="order-link">运营单 {{ item.operational_order_id }}</strong>
          </div>
          <div v-if="item.review_note" class="request-note"><AlertCircle :size="14" /><span>{{ item.review_note }}</span></div>
          <div v-if="isAdmin && ['pending_review', 'needs_info'].includes(item.status)" class="review-actions">
            <input v-model="reviewNote[item.id]" placeholder="可填写审核说明（选填）" maxlength="500" />
            <button class="approve-button" :disabled="busyId === item.id" @click="review(item, 'approve')"><Check :size="14" />通过并纳入运营</button>
            <button class="info-button" :disabled="busyId === item.id" @click="review(item, 'needs_info')">退回补充</button>
            <button class="reject-button" :disabled="busyId === item.id" @click="review(item, 'reject')">驳回</button>
          </div>
          <div v-else-if="!isAdmin && ['pending_review', 'needs_info'].includes(item.status)" class="review-actions user-actions"><button class="ghost-button" :disabled="busyId === item.id" @click="cancel(item)"><RotateCcw :size="14" />撤回申请</button></div>
        </article>
      </div>
    </article>
  </section>
</template>

<style scoped>
.order-request-center{display:flex;flex-direction:column;gap:18px}.order-notice{display:flex;align-items:center;gap:9px;padding:12px 14px;border:1px solid #dce8df;border-radius:10px;background:#f5faf6;color:#216b49;font-size:13px}.order-notice.error{border-color:#efd0cd;background:#fff4f2;color:#a43d37}.order-notice.info{background:#f2f6fb;color:#355e88}.order-notice button{margin-left:auto;border:0;background:transparent;color:inherit;cursor:pointer}.request-overview{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.request-overview article{display:flex;align-items:center;gap:12px;padding:16px 18px;border:1px solid #e2e9e4;border-radius:13px;background:#fff}.request-overview .icon{width:38px;height:38px;display:grid;place-items:center;border-radius:11px;background:#eaf6ee;color:#1b8755}.request-overview .icon.amber{background:#fff6e8;color:#bd7712}.request-overview .icon.blue{background:#edf4ff;color:#4178c5}.request-overview small,.request-overview strong{display:block}.request-overview small{color:#738078;font-size:12px}.request-overview strong{margin-top:3px;color:#17392a;font-size:23px}.request-user-grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(280px,.75fr);gap:18px}.request-form-card,.request-flow-card,.request-list-card{padding:23px;border:1px solid #e1e9e4;border-radius:15px;background:#fff;box-shadow:0 10px 25px rgba(24,61,43,.035)}.section-heading,.list-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.section-heading>svg{color:#178050}.section-kicker{display:flex;align-items:center;gap:6px;margin:0 0 7px;color:#178050;font-size:12px;font-weight:800}.section-heading h2,.list-heading h2{margin:0;color:#18392b;font-size:18px;letter-spacing:-.2px}.section-heading>div>span,.list-heading>div>span{display:block;margin-top:6px;color:#7b8982;font-size:12px}.request-form{display:flex;flex-direction:column;gap:14px;margin-top:20px}.form-grid{display:grid;gap:12px}.form-grid.two{grid-template-columns:1fr 1fr}.form-grid.three{grid-template-columns:1fr 1fr 1fr}.request-form label{display:flex;flex-direction:column;gap:6px}.request-form label>span{color:#405249;font-size:12px;font-weight:700}.request-form label b{color:#ca5548}.request-form input,.request-form select,.review-actions input{height:40px;border:1px solid #d9e2dc;border-radius:8px;padding:0 11px;background:#fbfcfb;color:#1d382b;font:inherit;font-size:13px;outline:none}.request-form input:focus,.request-form select:focus,.review-actions input:focus{border-color:#2d9966;box-shadow:0 0 0 3px rgba(45,153,102,.1)}.form-options{display:flex;align-items:flex-end;gap:17px;padding-top:2px}.form-options>label{flex:1}.form-options .check-option{flex-direction:row;align-items:center;gap:7px;padding-bottom:10px}.form-options .check-option input{width:16px;height:16px;accent-color:#168050}.form-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:3px;padding-top:15px;border-top:1px solid #edf1ee}.form-foot>span{display:flex;align-items:center;gap:6px;color:#718078;font-size:11px}.primary-button,.approve-button,.info-button,.reject-button,.ghost-button{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:8px;padding:10px 14px;font:inherit;font-size:12px;font-weight:800;cursor:pointer}.primary-button{background:#117347;color:#fff;box-shadow:0 5px 12px rgba(17,115,71,.14)}.primary-button:disabled,.approve-button:disabled,.info-button:disabled,.reject-button:disabled,.ghost-button:disabled{opacity:.55;cursor:not-allowed}.flow-list{display:flex;flex-direction:column;gap:0;margin:20px 0 17px;padding:0;list-style:none}.flow-list li{position:relative;display:flex;gap:11px;padding:0 0 20px}.flow-list li:not(:last-child)::after{content:"";position:absolute;left:13px;top:29px;width:1px;height:calc(100% - 19px);background:#dfe8e1}.flow-list i{position:relative;z-index:1;width:27px;height:27px;display:grid;place-items:center;border-radius:50%;background:#e9efeb;color:#718078;font-style:normal;font-size:12px;font-weight:800}.flow-list li.active i{background:#178050;color:#fff}.flow-list b,.flow-list span{display:block}.flow-list b{color:#274536;font-size:13px}.flow-list span{margin-top:4px;color:#829087;font-size:11px;line-height:1.45}.flow-note{display:flex;align-items:flex-start;gap:8px;padding:11px;border-radius:9px;background:#f0f7f2;color:#47735c;font-size:11px;line-height:1.5}.flow-note svg{flex:none;color:#198053}.request-list-card{padding-bottom:12px}.list-heading{padding-bottom:18px;border-bottom:1px solid #edf1ee}.list-actions{display:flex;align-items:center;gap:9px}.search-box{display:flex;align-items:center;gap:7px;width:225px;height:35px;padding:0 10px;border:1px solid #d9e2dc;border-radius:8px;color:#779087}.search-box input{width:100%;border:0;outline:0;background:transparent;color:#264435;font:inherit;font-size:12px}.ghost-button{border:1px solid #dbe5df;background:#fff;color:#3e6350}.request-list{display:flex;flex-direction:column}.request-item{display:grid;grid-template-columns:minmax(0,1fr) 175px;gap:10px 18px;padding:18px 4px;border-bottom:1px solid #edf1ee}.request-item:last-child{border-bottom:0}.request-item-main{min-width:0}.request-code{display:flex;align-items:center;gap:8px}.request-code strong{color:#204636;font-size:13px}.request-code small{color:#95a099;font-size:11px}.status-dot{width:8px;height:8px;border-radius:50%;background:#e0a52b}.status-dot.needs_info{background:#d28c1a}.status-dot.rejected,.status-dot.cancelled{background:#a6b0aa}.status-dot.converted{background:#1c9460}.request-summary{display:flex;flex-direction:column;gap:6px;margin:9px 0 0}.request-summary b{color:#294c3a;font-size:14px}.request-summary span{display:flex;align-items:center;gap:4px;color:#77867e;font-size:12px}.request-customer{display:flex;align-items:center;gap:8px;margin-top:10px;color:#9aa49e;font-size:11px}.request-customer b{margin-right:10px;color:#587164;font-size:12px}.request-item-side{display:flex;flex-direction:column;align-items:flex-end;gap:5px;text-align:right}.status-pill{display:inline-flex;align-items:center;padding:4px 9px;border-radius:99px;background:#fff4df;color:#af7216;font-size:11px;font-weight:800}.status-pill.needs_info{background:#fff4df}.status-pill.rejected,.status-pill.cancelled{background:#f0f2f1;color:#77847e}.status-pill.converted{background:#e7f5ec;color:#168052}.request-item-side small{color:#829087;font-size:11px;line-height:1.4}.order-link{color:#39745a;font-size:11px}.request-note{grid-column:1/-1;display:flex;align-items:flex-start;gap:7px;padding:9px 11px;border-radius:8px;background:#fffaf0;color:#94722d;font-size:11px;line-height:1.5}.request-note svg{flex:none;margin-top:1px}.review-actions{grid-column:1/-1;display:flex;align-items:center;gap:8px}.review-actions input{flex:1;min-width:160px}.approve-button{background:#178050;color:#fff}.info-button{border:1px solid #ead8ad;background:#fffaf0;color:#a4772b}.reject-button{border:1px solid #efd0cd;background:#fff5f3;color:#ab4942}.user-actions{justify-content:flex-end}.request-empty{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:7px;min-height:190px;color:#8b9891;font-size:12px}.request-empty svg{color:#9aaea2}.request-empty strong{color:#4f655a;font-size:14px}.request-empty span{font-size:12px}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:980px){.request-user-grid{grid-template-columns:1fr}.request-flow-card{order:-1}.request-item{grid-template-columns:1fr}.request-item-side{align-items:flex-start;text-align:left}.review-actions{flex-wrap:wrap}.review-actions input{flex-basis:100%}}
@media(max-width:640px){.request-overview{grid-template-columns:1fr}.form-grid.two,.form-grid.three{grid-template-columns:1fr}.form-options{align-items:stretch;flex-direction:column;gap:10px}.form-options .check-option{padding-bottom:0}.form-foot,.list-heading{align-items:stretch;flex-direction:column}.list-actions{justify-content:space-between}.search-box{width:auto;flex:1}.request-form-card,.request-flow-card,.request-list-card{padding:17px}.request-item{padding-left:0;padding-right:0}}
</style>
