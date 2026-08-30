<script setup lang="ts">
import {
  AlertCircle, Check, CircleDot, Eye, EyeOff, KeyRound, Layers3, LoaderCircle,
  Map, Pencil, Plus, Power, RefreshCw, ShieldCheck, TestTube2, X,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  activateMapConfig, createMapConfig, disableMapConfig, getMapConfigs,
  testMapConfig, updateMapConfig,
} from '../services/api'
import type { MapConfigInput, MapConfigView } from '../types/logistics'

const connections = ref<MapConfigView[]>([])
const loading = ref(true)
const saving = ref(false)
const testingId = ref<number>()
const drawerOpen = ref(false)
const editingId = ref<number>()
const showWebKey = ref(false)
const showSecurityCode = ref(false)
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const form = reactive<MapConfigInput>({
  name: '',
  provider: 'amap',
  web_key: '',
  security_code: '',
  map_style: 'whitesmoke',
  enabled: true,
})
const editing = computed(() => connections.value.find(item => item.id === editingId.value))
const enabled = computed(() => connections.value.find(item => item.enabled))
const healthyCount = computed(() => connections.value.filter(item => item.last_test_status === 'success').length)

function formatTime(value?: string) {
  if (!value) return '尚未测试'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function resetForm(item?: MapConfigView) {
  editingId.value = item?.id
  Object.assign(form, {
    name: item?.name ?? '',
    provider: 'amap',
    web_key: '',
    security_code: '',
    map_style: item?.map_style ?? 'whitesmoke',
    enabled: item?.enabled ?? true,
  })
  showWebKey.value = false
  showSecurityCode.value = false
}

function openCreate() { resetForm(); drawerOpen.value = true }
function openEdit(item: MapConfigView) { resetForm(item); drawerOpen.value = true }
function closeDrawer() { if (!saving.value) drawerOpen.value = false }

async function load() {
  loading.value = true
  try { connections.value = (await getMapConfigs()).items }
  catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '地图连接加载失败' }
  } finally { loading.value = false }
}

async function save() {
  saving.value = true
  notice.value = undefined
  try {
    const payload = {
      ...form,
      web_key: form.web_key?.trim() || undefined,
      security_code: form.security_code?.trim() || undefined,
    }
    if (editingId.value) await updateMapConfig(editingId.value, payload)
    else await createMapConfig(payload)
    drawerOpen.value = false
    notice.value = { kind: 'success', text: editingId.value ? '地图连接已更新' : '地图连接已加密保存' }
    await load()
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '保存失败' }
  } finally { saving.value = false }
}

async function testConnection(item: MapConfigView) {
  testingId.value = item.id
  notice.value = undefined
  try {
    const result = await testMapConfig(item.id)
    notice.value = {
      kind: result.success ? 'success' : 'error',
      text: `${item.name}：${result.message}（${result.latency_ms} ms）`,
    }
    await load()
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '连接测试失败' }
  } finally { testingId.value = undefined }
}

async function toggleActive(item: MapConfigView) {
  try {
    if (item.enabled) await disableMapConfig(item.id)
    else await activateMapConfig(item.id)
    notice.value = {
      kind: 'success',
      text: item.enabled ? '已切换为离线运营地图' : `已启用“${item.name}”`,
    }
    await load()
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '状态更新失败' }
  }
}

onMounted(load)
</script>

<template>
  <section class="map-settings">
    <div class="settings-toolbar">
      <div>
        <p><Map :size="16" /> 地图服务管理</p>
        <h2>地图连接</h2>
        <span>统一管理道路底图服务。未启用第三方连接时，平台自动使用离线运营地图。</span>
      </div>
      <button class="primary-action" @click="openCreate"><Plus :size="18" />新建连接</button>
    </div>

    <div v-if="notice" class="notice" :class="notice.kind">
      <Check v-if="notice.kind === 'success'" :size="17" />
      <AlertCircle v-else :size="17" />
      <span>{{ notice.text }}</span>
      <button aria-label="关闭提示" @click="notice = undefined"><X :size="15" /></button>
    </div>

    <div class="summary-row">
      <article><span><Layers3 :size="19" /></span><div><small>当前地图</small><strong>{{ enabled ? '高德道路地图' : '离线运营地图' }}</strong></div></article>
      <article><span><Power :size="19" /></span><div><small>第三方连接</small><strong>{{ connections.length }}</strong></div></article>
      <article><span><ShieldCheck :size="19" /></span><div><small>最近测试正常</small><strong>{{ healthyCount }}</strong></div></article>
    </div>

    <article class="connection-table">
      <div class="table-title">
        <div><h3>连接列表</h3><p>Web Key 与安全密钥仅在新建或轮换时录入，保存后只显示掩码。</p></div>
        <button :disabled="loading" @click="load"><RefreshCw :class="{ spin: loading }" :size="16" />刷新</button>
      </div>
      <div class="table-scroll">
        <div class="connection-row table-head"><span>名称</span><span>服务商</span><span>访问凭据</span><span>地图样式</span><span>状态</span><span>最近测试</span><span>操作</span></div>
        <div v-for="item in connections" :key="item.id" class="connection-row">
          <div class="name-cell"><strong>{{ item.name }}</strong><small>{{ item.updated_by ?? item.created_by ?? '系统' }} · {{ formatTime(item.updated_at) }}</small></div>
          <div class="provider-cell"><strong>高德地图</strong><small>Web JavaScript API 2.0</small></div>
          <div class="secret-cell"><span><KeyRound :size="12" />{{ item.web_key_masked }}</span><small>{{ item.security_code_masked }}</small></div>
          <code>{{ item.map_style }}</code>
          <span class="status-badge" :class="{ enabled: item.enabled }"><i />{{ item.enabled ? '默认启用' : '已停用' }}</span>
          <div class="test-cell" :class="item.last_test_status"><strong><CircleDot :size="13" />{{ item.last_test_status === 'success' ? '正常' : item.last_test_status === 'failed' ? '失败' : '未测试' }}</strong><small>{{ formatTime(item.last_tested_at) }}</small></div>
          <div class="row-actions">
            <button :disabled="testingId === item.id" @click="testConnection(item)"><LoaderCircle v-if="testingId === item.id" class="spin" :size="14" /><TestTube2 v-else :size="14" />测试</button>
            <button @click="openEdit(item)"><Pencil :size="14" />编辑</button>
            <button class="power-action" :class="{ on: item.enabled }" @click="toggleActive(item)">{{ item.enabled ? '停用' : '设为默认' }}</button>
          </div>
        </div>
        <div v-if="loading" class="empty-state"><LoaderCircle class="spin" :size="25" /><strong>正在读取地图连接</strong></div>
        <div v-else-if="!connections.length" class="empty-state"><Map :size="31" /><strong>当前使用离线运营地图</strong><span>添加高德 Web JS 连接后，可切换到真实道路底图。</span><button @click="openCreate"><Plus :size="16" />新建连接</button></div>
      </div>
      <footer>停用全部第三方连接后，调度页面会自动回退到离线地图。</footer>
    </article>

    <aside class="security-note">
      <ShieldCheck :size="21" />
      <div><strong>安全代理与公网分享</strong><p>安全密钥在服务端加密保存并通过同源代理使用，不返回给浏览器。本机、固定域名和临时分享链接都会优先使用高德道路地图；临时链接每次域名随机生成，请将本次分享域名加入高德 Web JS Key 白名单后刷新页面。</p></div>
    </aside>

    <Teleport to="body">
      <div v-if="drawerOpen" class="drawer-layer" @mousedown.self="closeDrawer">
        <aside class="config-drawer" role="dialog" aria-modal="true" :aria-label="editingId ? '编辑地图连接' : '新建地图连接'">
          <header><div><small>{{ editingId ? '更新道路地图服务信息' : '创建道路地图服务凭据' }}</small><h3>{{ editingId ? '编辑地图连接' : '新建地图连接' }}</h3></div><button aria-label="关闭" @click="closeDrawer"><X :size="21" /></button></header>
          <form id="map-connection-form" @submit.prevent="save">
            <label><span>配置名称 <b>*</b></span><input v-model.trim="form.name" placeholder="例如：生产环境高德地图" required minlength="2" /></label>
            <label><span>服务商</span><select v-model="form.provider" disabled><option value="amap">高德地图 Web JS API 2.0</option></select></label>
            <label>
              <span>Web JS Key <b v-if="!editingId">*</b></span>
              <div class="secret-input"><input v-model="form.web_key" :required="!editingId" :type="showWebKey ? 'text' : 'password'" autocomplete="new-password" :placeholder="editing ? `已配置 ${editing.web_key_masked}，留空则不修改` : '请输入 Web 端（JS API）Key'" /><button type="button" aria-label="切换 Web Key 可见性" @click="showWebKey = !showWebKey"><EyeOff v-if="showWebKey" :size="17" /><Eye v-else :size="17" /></button></div>
            </label>
            <label>
              <span>securityJsCode <b v-if="!editingId">*</b></span>
              <div class="secret-input"><input v-model="form.security_code" :required="!editingId" :type="showSecurityCode ? 'text' : 'password'" autocomplete="new-password" :placeholder="editing ? `已配置 ${editing.security_code_masked}，留空则不修改` : '请输入与 Key 配套的安全密钥'" /><button type="button" aria-label="切换安全密钥可见性" @click="showSecurityCode = !showSecurityCode"><EyeOff v-if="showSecurityCode" :size="17" /><Eye v-else :size="17" /></button></div>
              <small>安全密钥保存后不可回显，由服务端代理使用。</small>
            </label>
            <label><span>地图样式</span><select v-model="form.map_style"><option value="whitesmoke">浅灰道路图</option><option value="normal">标准地图</option><option value="fresh">清新地图</option><option value="light">亮色地图</option></select></label>
            <label class="default-toggle"><div><strong>保存后设为默认地图</strong><small>启用后会自动停用当前第三方地图连接。</small></div><input v-model="form.enabled" type="checkbox" /></label>
            <div class="security-callout"><ShieldCheck :size="18" /><p><b>凭据保护</b><span>两项凭据均使用服务端密钥加密入库，列表和审计日志只记录状态。</span></p></div>
          </form>
          <footer><button class="cancel" :disabled="saving" @click="closeDrawer">取消</button><button class="save" form="map-connection-form" :disabled="saving"><LoaderCircle v-if="saving" class="spin" :size="17" /><ShieldCheck v-else :size="17" />{{ saving ? '正在保存…' : '保存连接' }}</button></footer>
        </aside>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.map-settings{display:flex;flex-direction:column;gap:18px;color:#22372d}.settings-toolbar{display:flex;justify-content:space-between;align-items:flex-start;gap:24px}.settings-toolbar p{display:flex;align-items:center;gap:7px;margin:0 0 7px;color:#18754e;font-size:13px;font-weight:800}.settings-toolbar h2{margin:0;font-size:24px}.settings-toolbar span{display:block;margin-top:9px;color:#718078;font-size:13px}.primary-action{height:42px;display:flex;align-items:center;gap:8px;padding:0 16px;border:0;border-radius:9px;background:#126b47;color:#fff;font-weight:800;cursor:pointer}.notice{display:flex;align-items:flex-start;gap:8px;padding:11px 13px;border-radius:9px;font-size:13px}.notice.success{border:1px solid #cce6d6;background:#eef8f2;color:#146d46}.notice.error{border:1px solid #efcfcc;background:#fff1f0;color:#a93e38}.notice button{margin-left:auto;border:0;background:transparent;color:inherit;cursor:pointer}.summary-row{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:12px}.summary-row article{display:flex;align-items:center;gap:13px;padding:17px 18px;border:1px solid #e0e6e2;border-radius:11px;background:#fff}.summary-row article>span{width:38px;height:38px;display:grid;place-items:center;border-radius:50%;background:#eaf5ef;color:#14724b}.summary-row small,.summary-row strong{display:block}.summary-row small{color:#7a867f;font-size:12px}.summary-row strong{margin-top:4px;font-size:18px}.connection-table{overflow:hidden;border:1px solid #dde4df;border-radius:12px;background:#fff}.table-title{display:flex;align-items:center;justify-content:space-between;padding:17px 19px;border-bottom:1px solid #e5e9e6}.table-title h3{margin:0;font-size:16px}.table-title p{margin:5px 0 0;color:#7c8981;font-size:12px}.table-title button{display:flex;align-items:center;gap:6px;border:0;background:transparent;color:#4f675a;cursor:pointer}.table-scroll{overflow-x:auto}.connection-row{min-width:1050px;display:grid;grid-template-columns:1.15fr .9fr 1.25fr .65fr .7fr .85fr 1.35fr;align-items:center;gap:13px;min-height:72px;padding:0 18px;border-bottom:1px solid #e8ece9;font-size:13px}.table-head{min-height:42px;background:#f6f8f6;color:#6e7b74;font-size:12px;font-weight:800}.name-cell strong,.name-cell small,.provider-cell strong,.provider-cell small,.test-cell strong,.test-cell small,.secret-cell span,.secret-cell small{display:block}.name-cell small,.provider-cell small,.secret-cell small,.test-cell small{margin-top:5px;color:#849088;font-size:10px}.secret-cell span{display:flex;align-items:center;gap:5px;color:#315741;font-size:11px}.connection-row code{font-size:11px;color:#28523d}.status-badge{width:max-content;display:flex;align-items:center;gap:6px;padding:5px 8px;border-radius:20px;background:#f0f2f0;color:#6d7972;font-size:11px}.status-badge i{width:6px;height:6px;border-radius:50%;background:#9aa39e}.status-badge.enabled{background:#e9f6ee;color:#157249}.status-badge.enabled i{background:#1d9b61}.test-cell strong{display:flex;align-items:center;gap:5px;font-size:12px;color:#6d7872}.test-cell.success strong{color:#15734a}.test-cell.failed strong{color:#bd433d}.row-actions{display:flex;align-items:center;gap:3px}.row-actions button{height:32px;display:flex;align-items:center;gap:5px;padding:0 7px;border:0;border-radius:6px;background:transparent;color:#176e49;font-size:11px;cursor:pointer}.row-actions button:hover{background:#edf5f0}.row-actions .power-action{color:#5f6f66}.row-actions .power-action.on{color:#a6443f}.connection-table>footer{padding:12px 18px;background:#fafbfa;color:#849088;font-size:11px}.empty-state{min-height:230px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;color:#789086}.empty-state strong{color:#40564a}.empty-state span{font-size:12px}.empty-state button{display:flex;align-items:center;gap:6px;margin-top:5px;border:0;border-radius:8px;padding:9px 13px;background:#e9f4ee;color:#126e48;font-weight:700;cursor:pointer}.security-note{display:flex;align-items:flex-start;gap:12px;padding:16px 18px;border:1px solid #dce7df;border-radius:11px;background:#f2f8f4;color:#176b47}.security-note strong{font-size:13px}.security-note p{margin:5px 0 0;color:#63766b;font-size:12px;line-height:1.6}.drawer-layer{position:fixed;inset:0;z-index:100;background:rgba(18,38,28,.36);backdrop-filter:blur(1px)}.config-drawer{position:absolute;right:0;top:0;width:min(520px,100%);height:100%;display:grid;grid-template-rows:auto 1fr auto;background:#fff;box-shadow:-14px 0 40px rgba(14,45,29,.13)}.config-drawer>header{height:78px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid #e2e7e4}.config-drawer header small{color:#7b8981}.config-drawer h3{margin:5px 0 0;font-size:19px}.config-drawer header button{width:40px;height:40px;border:0;border-radius:8px;background:transparent;color:#627168;cursor:pointer}.config-drawer form{overflow-y:auto;padding:23px 24px;display:flex;flex-direction:column;gap:18px}.config-drawer form>label{display:flex;flex-direction:column;gap:7px}.config-drawer label>span{font-size:13px;font-weight:750}.config-drawer label b{color:#cf433c}.config-drawer input:not([type=checkbox]),.config-drawer select{width:100%;height:44px;border:1px solid #d7dfda;border-radius:8px;padding:0 12px;background:#fff;color:#263b30;font:inherit;outline:none}.config-drawer input:focus,.config-drawer select:focus{border-color:#187a50;box-shadow:0 0 0 3px rgba(24,122,80,.11)}.config-drawer label small{color:#829087;font-size:11px;line-height:1.5}.secret-input{position:relative}.secret-input input{padding-right:44px!important}.secret-input button{position:absolute;right:3px;top:3px;width:38px;height:38px;border:0;background:transparent;color:#75837b;cursor:pointer}.default-toggle{flex-direction:row!important;align-items:center;justify-content:space-between;padding:14px;border:1px solid #e0e6e2;border-radius:9px}.default-toggle strong,.default-toggle small{display:block}.default-toggle input{width:20px;height:20px;accent-color:#167a50}.security-callout{display:flex;gap:10px;padding:13px;border-radius:9px;background:#edf6f1;color:#176f4a}.security-callout p{margin:0}.security-callout b,.security-callout span{display:block}.security-callout span{margin-top:5px;color:#60746a;font-size:11px;line-height:1.5}.config-drawer>footer{height:72px;display:flex;justify-content:flex-end;align-items:center;gap:9px;padding:0 24px;border-top:1px solid #e2e7e4}.config-drawer>footer button{height:40px;padding:0 15px;border-radius:8px;font-weight:750;cursor:pointer}.config-drawer .cancel{border:1px solid #d5ded8;background:#fff;color:#53665b}.config-drawer .save{display:flex;align-items:center;gap:7px;border:0;background:#126b47;color:#fff}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:760px){.settings-toolbar{flex-direction:column}.primary-action{width:100%;justify-content:center}.summary-row{grid-template-columns:1fr}.config-drawer{width:100%}}
</style>
