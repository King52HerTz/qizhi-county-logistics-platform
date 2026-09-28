<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { CheckCircle2, ClipboardList, RefreshCw, Snowflake, TriangleAlert, Warehouse } from '@lucide/vue'
import {
  createColdChainBooking,
  getColdChainBookings,
  getColdChainOverview,
  getColdChainStores,
} from '../services/api'
import type {
  ColdStoreBookingView,
  ColdStorePurpose,
  ColdStoreView,
  TemperatureOverview,
} from '../types/logistics'

const busy = ref(false)
const submitting = ref(false)
const error = ref('')
const message = ref('')
const stores = ref<ColdStoreView[]>([])
const bookings = ref<ColdStoreBookingView[]>([])
const overview = ref<TemperatureOverview>()

const form = reactive({
  cold_store_id: '',
  booking_date: new Date().toISOString().slice(0, 10),
  purpose: 'precool' as ColdStorePurpose,
  tons: 2,
  note: '',
})

const storeTypeLabels: Record<string, string> = {
  county_hub: '县域共用库',
  township: '乡镇共享库',
  field_precool: '田头预冷点',
}
const zoneLabels: Record<string, string> = {
  chilled: '冷藏 0~4℃',
  frozen: '冷冻 ≤-18℃',
  ambient: '常温中转',
}
const purposeLabels: Record<string, string> = {
  precool: '采收预冷',
  short_storage: '短期存储',
  transit: '干线中转',
}
const statusLabels: Record<string, string> = {
  reserved: '已预约',
  active: '占用中',
  completed: '已完成',
  cancelled: '已取消',
}

const totalCapacity = computed(() =>
  stores.value.reduce((sum, item) => sum + item.capacity_tons, 0),
)
const totalBooked = computed(() =>
  stores.value.reduce((sum, item) => sum + item.booked_tons, 0),
)

function usageClass(store: ColdStoreView) {
  const ratio = store.capacity_tons ? store.booked_tons / store.capacity_tons : 0
  if (ratio >= 0.9) return 'danger'
  if (ratio >= 0.7) return 'warning'
  return 'ok'
}

async function loadData() {
  busy.value = true
  error.value = ''
  try {
    const [storeList, bookingList, overviewData] = await Promise.all([
      getColdChainStores(),
      getColdChainBookings(20),
      getColdChainOverview(),
    ])
    stores.value = storeList.items
    bookings.value = bookingList.items
    overview.value = overviewData
    if (!form.cold_store_id && stores.value.length) {
      form.cold_store_id = stores.value[0].id
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '冷链仓储数据加载失败'
  } finally {
    busy.value = false
  }
}

async function submitBooking() {
  submitting.value = true
  message.value = ''
  error.value = ''
  try {
    await createColdChainBooking({
      cold_store_id: form.cold_store_id,
      booking_date: form.booking_date,
      purpose: form.purpose,
      tons: Number(form.tons),
      note: form.note || null,
    })
    message.value = '共享库容预约已登记，可在预约记录中跟踪状态。'
    form.note = ''
    await loadData()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '预约提交失败'
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="cold-storage">
    <header class="page-heading">
      <div>
        <h1>冷链仓储共享调度</h1>
        <p>县域共用库 · 乡镇共享库 · 田头预冷点 · 库容与冷链运力协同</p>
      </div>
      <div class="heading-actions">
        <button class="ghost-button" :disabled="busy" @click="loadData">
          <RefreshCw :size="16" />{{ busy ? '刷新中' : '刷新数据' }}
        </button>
      </div>
    </header>

    <div class="boundary-note">
      <TriangleAlert :size="15" />
      <span>
        演示边界：冷库台账与库容来自祁东县研究资料汇总口径，预约与利用率是演示样本，不代表实时库存；
        冷链订单与冷链车辆的匹配仍由确定性求解器校验。
      </span>
    </div>

    <div v-if="error" class="state-message error">{{ error }}</div>
    <div v-else-if="message" class="state-message ok"><CheckCircle2 :size="14" />{{ message }}</div>

    <section class="metric-strip">
      <div><span>共享冷库</span><strong>{{ stores.length }}</strong><small>县域 {{ stores.filter(item => item.store_type === 'county_hub').length }} · 乡镇 {{ stores.filter(item => item.store_type === 'township').length }} · 田头 {{ stores.filter(item => item.store_type === 'field_precool').length }}</small></div>
      <div><span>台账总库容</span><strong>{{ totalCapacity.toLocaleString() }} 吨</strong><small>汇总研究资料核对值</small></div>
      <div><span>今日已约</span><strong>{{ totalBooked.toFixed(1) }} 吨</strong><small>预约 + 占用合计</small></div>
      <div><span>温控采集点</span><strong>{{ overview?.active_sensors ?? 0 }}</strong><small>启用 {{ overview?.sensor_total ?? 0 }} 个</small></div>
    </section>

    <div class="main-grid">
      <section class="panel store-panel">
        <div class="panel-title">
          <div><h2>共享冷库台账</h2><p>库容占用按当日预约与占用合计计算</p></div>
          <Warehouse :size="20" />
        </div>
        <p v-if="!stores.length" class="empty-state">暂无冷库台账，请刷新或检查演示数据。</p>
        <div v-else class="store-list">
          <article v-for="store in stores" :key="store.id" class="store-card">
            <div class="store-head">
              <strong>{{ store.name }}</strong>
              <span class="badge type">{{ storeTypeLabels[store.store_type] }}</span>
              <span class="badge zone">{{ zoneLabels[store.temperature_zone] }}</span>
            </div>
            <div class="store-meta">
              <span>{{ store.node_name ?? '未绑定网点' }}</span>
              <span v-if="store.contact">☎ {{ store.contact }}</span>
            </div>
            <div class="usage-bar">
              <div class="usage-fill" :class="usageClass(store)" :style="{ width: `${Math.min(100, store.capacity_tons ? (store.booked_tons / store.capacity_tons) * 100 : 0)}%` }" />
            </div>
            <div class="usage-caption">
              <span>已约 {{ store.booked_tons.toFixed(1) }} / {{ store.capacity_tons }} 吨</span>
              <span>可用 {{ store.available_tons.toFixed(1) }} 吨</span>
              <span v-if="store.latest_temperature_c !== null">库温 {{ store.latest_temperature_c.toFixed(1) }}℃</span>
            </div>
          </article>
        </div>
      </section>

      <aside class="side-column">
        <section class="panel">
          <div class="panel-title">
            <div><h2>共享库容预约</h2><p>预冷、短储与中转占库登记</p></div>
            <ClipboardList :size="20" />
          </div>
          <form class="booking-form" @submit.prevent="submitBooking">
            <label><span>目标冷库</span>
              <select v-model="form.cold_store_id" required>
                <option v-for="store in stores" :key="store.id" :value="store.id">
                  {{ store.name }}（可用 {{ store.available_tons.toFixed(1) }} 吨）
                </option>
              </select>
            </label>
            <label><span>预约日期</span><input v-model="form.booking_date" type="date" required /></label>
            <label><span>用途</span>
              <select v-model="form.purpose">
                <option value="precool">采收预冷</option>
                <option value="short_storage">短期存储</option>
                <option value="transit">干线中转</option>
              </select>
            </label>
            <label><span>吨位（吨）</span><input v-model.number="form.tons" type="number" min="0.1" max="10000" step="0.1" required /></label>
            <label><span>备注</span><input v-model="form.note" type="text" maxlength="200" placeholder="如：黄花菜采收季预冷" /></label>
            <button class="primary-button" :disabled="submitting || !stores.length">
              <Snowflake :size="16" />{{ submitting ? '提交中' : '登记预约' }}
            </button>
          </form>
        </section>

        <section class="panel">
          <div class="panel-title">
            <div><h2>最近预约记录</h2><p>调度员与管理员可跟踪占用状态</p></div>
            <ClipboardList :size="20" />
          </div>
          <p v-if="!bookings.length" class="empty-state">暂无预约记录，提交首个共享库容预约后将在此留痕。</p>
          <table v-else class="booking-table">
            <thead>
              <tr><th>冷库</th><th>日期</th><th>用途</th><th>吨位</th><th>状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="booking in bookings" :key="booking.id">
                <td>{{ booking.cold_store_name }}</td>
                <td>{{ booking.booking_date }}</td>
                <td>{{ purposeLabels[booking.purpose] }}</td>
                <td>{{ booking.tons.toFixed(1) }}</td>
                <td><span class="badge status">{{ statusLabels[booking.status] }}</span></td>
              </tr>
            </tbody>
          </table>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.cold-storage {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
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
.metric-strip small {
  font-size: 11.5px;
  color: #8b9791;
}
.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
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
.side-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.store-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.store-card {
  border: 1px solid #e3ece7;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.store-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.store-head strong {
  font-size: 13.5px;
  color: #30473b;
}
.badge {
  font-size: 11px;
  border-radius: 999px;
  padding: 2px 8px;
  background: #eaf4ee;
  color: #0d5b3d;
}
.badge.zone {
  background: #eef3f8;
  color: #3e5368;
}
.badge.status {
  background: #f1f6f3;
}
.store-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #66776e;
}
.usage-bar {
  height: 8px;
  background: #eef3f0;
  border-radius: 999px;
  overflow: hidden;
}
.usage-fill {
  height: 100%;
  border-radius: 999px;
  background: #178052;
}
.usage-fill.warning {
  background: #f3b63e;
}
.usage-fill.danger {
  background: #c9563c;
}
.usage-caption {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  color: #8b9791;
}
.booking-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.booking-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12.5px;
  color: #51625a;
}
.booking-form input,
.booking-form select {
  border: 1px solid #c9d8cf;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #0d5b3d;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13.5px;
  cursor: pointer;
}
.primary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.empty-state {
  color: #8b9791;
  font-size: 12.5px;
  margin: 6px 0;
}
.booking-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.booking-table th,
.booking-table td {
  text-align: left;
  padding: 7px 6px;
  border-bottom: 1px solid #eef3f0;
  color: #51625a;
}
.booking-table th {
  color: #8b9791;
  font-weight: 500;
}
@media (max-width: 1100px) {
  .main-grid,
  .metric-strip {
    grid-template-columns: 1fr;
  }
  .store-list {
    grid-template-columns: 1fr;
  }
}
</style>
