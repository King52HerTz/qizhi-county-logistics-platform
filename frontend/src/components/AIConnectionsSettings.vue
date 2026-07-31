<script setup lang="ts">
import { AlertCircle, Check, CircleDot, Eye, EyeOff, KeyRound, Link2, LoaderCircle, Pencil, Plus, Power, RefreshCw, ServerCog, ShieldCheck, X } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { activateAIConfig, createAIConfig, disableAIConfig, getAIConfigs, testAIConfigById, updateAIConfig } from '../services/api'
import type { AIConfigInput, AIConfigView } from '../types/logistics'

const connections = ref<AIConfigView[]>([])
const loading = ref(true)
const saving = ref(false)
const testingId = ref<number>()
const drawerOpen = ref(false)
const editingId = ref<number>()
const showSecret = ref(false)
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const form = reactive<AIConfigInput>({
  name: '', description: '', provider: 'openai-compatible',
  base_url: 'https://api.openai.com/v1', model_name: '', api_key: '',
  enabled: false, temperature: 0.2,
})
const providers = [
  ['openai-compatible', 'OpenAI 兼容服务'],
  ['openai', 'OpenAI'],
  ['deepseek', 'DeepSeek'],
  ['qwen', '通义千问'],
  ['custom', '其他兼容服务'],
]
const configuredCount = computed(() => connections.value.length)
const enabledCount = computed(() => connections.value.filter(item => item.enabled).length)
const healthyCount = computed(() => connections.value.filter(item => item.last_test_status === 'success').length)
const editing = computed(() => connections.value.find(item => item.id === editingId.value))

function providerName(provider: string) {
  return providers.find(item => item[0] === provider)?.[1] ?? provider
}
function formatTime(value?: string) {
  if (!value) return '尚未测试'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}
function resetForm(item?: AIConfigView) {
  editingId.value = item?.id
  Object.assign(form, {
    name: item?.name ?? '',
    description: item?.description ?? '',
    provider: item?.provider ?? 'openai-compatible',
    base_url: item?.base_url ?? 'https://api.openai.com/v1',
    model_name: item?.model_name ?? '',
    api_key: '',
    enabled: item?.enabled ?? false,
    temperature: item?.temperature ?? 0.2,
  })
  showSecret.value = false
}
function openCreate() { resetForm(); drawerOpen.value = true }
function openEdit(item: AIConfigView) { resetForm(item); drawerOpen.value = true }
function closeDrawer() { if (!saving.value) drawerOpen.value = false }

function applyProviderPreset() {
  const presets: Record<string, [string, string]> = {
    openai: ['https://api.openai.com/v1', 'gpt-4.1-mini'],
    deepseek: ['https://api.deepseek.com', 'deepseek-chat'],
    qwen: ['https://dashscope.aliyuncs.com/compatible-mode/v1', 'qwen-plus'],
  }
  const preset = presets[form.provider]
  if (preset) [form.base_url, form.model_name] = preset
}

async function load() {
  loading.value = true
  try { connections.value = (await getAIConfigs()).items }
  catch (cause) { notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '连接列表加载失败' } }
  finally { loading.value = false }
}
async function save() {
  saving.value = true
  notice.value = undefined
  try {
    const payload = { ...form, api_key: form.api_key?.trim() || undefined }
    if (editingId.value) await updateAIConfig(editingId.value, payload)
    else await createAIConfig(payload)
    drawerOpen.value = false
    notice.value = { kind: 'success', text: editingId.value ? '连接配置已更新' : 'AI 连接已加密保存' }
    await load()
  } catch (cause) { notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '保存失败' } }
  finally { saving.value = false }
}
async function testConnection(item: AIConfigView) {
  testingId.value = item.id
  notice.value = undefined
  try {
    const result = await testAIConfigById(item.id)
    notice.value = { kind: result.success ? 'success' : 'error', text: `${item.name}：${result.message}（${result.latency_ms} ms）` }
    await load()
  } catch (cause) { notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '连接测试失败' } }
  finally { testingId.value = undefined }
}
async function toggleActive(item: AIConfigView) {
  try {
    if (item.enabled) await disableAIConfig(item.id)
    else await activateAIConfig(item.id)
    notice.value = { kind: 'success', text: item.enabled ? '已停用默认连接' : `已将“${item.name}”设为默认连接` }
    await load()
  } catch (cause) { notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '状态更新失败' } }
}

onMounted(load)
</script>

<template>
  <section class="ai-settings">
    <div class="settings-toolbar">
      <div><p><ServerCog :size="16" /> 模型服务管理</p><h2>AI 服务连接</h2><span>统一管理模型服务、访问凭据和默认启用状态。路径求解仍由 OR-Tools 确定性完成。</span></div>
      <button class="primary-action" @click="openCreate"><Plus :size="18" />新建连接</button>
    </div>

    <div v-if="notice" class="notice" :class="notice.kind"><Check v-if="notice.kind === 'success'" :size="17" /><AlertCircle v-else :size="17" /><span>{{ notice.text }}</span><button @click="notice = undefined"><X :size="15" /></button></div>

    <div class="summary-row">
      <article><span><Link2 :size="18" /></span><div><small>已配置</small><strong>{{ configuredCount }}</strong></div></article>
      <article><span><Power :size="18" /></span><div><small>已启用</small><strong>{{ enabledCount }}</strong></div></article>
      <article><span><ShieldCheck :size="18" /></span><div><small>最近测试正常</small><strong>{{ healthyCount }}</strong></div></article>
    </div>

    <article class="connection-table">
      <div class="table-title"><div><h3>连接列表</h3><p>API Key 仅在新建或轮换时录入，保存后只显示掩码。</p></div><button :disabled="loading" @click="load"><RefreshCw :class="{ spin: loading }" :size="16" />刷新</button></div>
      <div class="table-scroll">
        <div class="connection-row table-head"><span>名称</span><span>服务商 / Base URL</span><span>模型</span><span>状态</span><span>最近测试</span><span>更新人</span><span>操作</span></div>
        <div v-for="item in connections" :key="item.id" class="connection-row">
          <div class="name-cell"><strong>{{ item.name }}</strong><small><KeyRound :size="12" />{{ item.api_key_masked }}</small></div>
          <div class="provider-cell"><strong>{{ providerName(item.provider) }}</strong><small>{{ item.base_url }}</small></div>
          <code>{{ item.model_name }}</code>
          <span class="status-badge" :class="{ enabled: item.enabled }"><i />{{ item.enabled ? '默认启用' : '已停用' }}</span>
          <div class="test-cell" :class="item.last_test_status"><strong><CircleDot :size="13" />{{ item.last_test_status === 'success' ? '正常' : item.last_test_status === 'failed' ? '失败' : '未测试' }}</strong><small>{{ formatTime(item.last_tested_at) }}</small></div>
          <div class="updated-cell"><span>{{ item.updated_by ?? item.created_by ?? '系统' }}</span><small>{{ formatTime(item.updated_at) }}</small></div>
          <div class="row-actions">
            <button :disabled="testingId === item.id" @click="testConnection(item)"><LoaderCircle v-if="testingId === item.id" class="spin" :size="14" /><RefreshCw v-else :size="14" />测试</button>
            <button @click="openEdit(item)"><Pencil :size="14" />编辑</button>
            <button class="power-action" :class="{ on: item.enabled }" @click="toggleActive(item)">{{ item.enabled ? '停用' : '设为默认' }}</button>
          </div>
        </div>
        <div v-if="loading" class="empty-state"><LoaderCircle class="spin" :size="25" /><strong>正在读取连接配置</strong></div>
        <div v-else-if="!connections.length" class="empty-state"><ServerCog :size="30" /><strong>尚未添加 AI 连接</strong><span>新建连接后可独立测试，再决定是否设为默认。</span><button @click="openCreate"><Plus :size="16" />新建连接</button></div>
      </div>
      <footer v-if="connections.length">共 {{ connections.length }} 条连接 · 任意时刻仅允许一个默认启用连接</footer>
    </article>

    <Teleport to="body">
      <div v-if="drawerOpen" class="drawer-layer" @mousedown.self="closeDrawer">
        <aside class="config-drawer" role="dialog" aria-modal="true" :aria-label="editingId ? '编辑 AI 连接' : '新建 AI 连接'">
          <header><div><small>{{ editingId ? '更新连接信息' : '创建新的模型服务凭据' }}</small><h3>{{ editingId ? '编辑 AI 连接' : '新建 AI 连接' }}</h3></div><button aria-label="关闭" @click="closeDrawer"><X :size="21" /></button></header>
          <form id="ai-connection-form" @submit.prevent="save">
            <label><span>配置名称 <b>*</b></span><input v-model.trim="form.name" placeholder="例如：生产推理服务" required minlength="2" /></label>
            <label><span>服务商 <b>*</b></span><select v-model="form.provider" @change="applyProviderPreset"><option v-for="item in providers" :key="item[0]" :value="item[0]">{{ item[1] }}</option></select></label>
            <label><span>API Base URL <b>*</b></span><input v-model.trim="form.base_url" type="url" placeholder="https://api.example.com/v1" required /></label>
            <label><span>模型 ID <b>*</b></span><input v-model.trim="form.model_name" placeholder="例如：gpt-4.1-mini" required /></label>
            <label>
              <span>API Key <b v-if="!editingId">*</b></span>
              <div class="secret-input"><input v-model="form.api_key" :required="!editingId" :type="showSecret ? 'text' : 'password'" autocomplete="new-password" :placeholder="editing ? `已配置 ${editing.api_key_masked}，留空则不修改` : '请输入 API Key'" /><button type="button" @click="showSecret = !showSecret"><EyeOff v-if="showSecret" :size="17" /><Eye v-else :size="17" /></button></div>
              <small>密钥将加密保存，保存后不可回显；编辑时留空表示保留原密钥。</small>
            </label>
            <label><span>生成温度 <output>{{ Number(form.temperature).toFixed(1) }}</output></span><input v-model.number="form.temperature" class="range" type="range" min="0" max="2" step="0.1" /><small>0 更稳定，2 更随机。调度解释建议使用 0.2–0.5。</small></label>
            <label><span>描述（选填）</span><textarea v-model.trim="form.description" maxlength="500" placeholder="说明用途、环境或负责人" /><small class="counter">{{ form.description?.length ?? 0 }} / 500</small></label>
            <label class="default-toggle"><div><strong>保存后设为默认连接</strong><small>启用后会自动停用当前默认连接。</small></div><input v-model="form.enabled" type="checkbox" /></label>
            <div class="security-callout"><ShieldCheck :size="18" /><p><b>安全存储</b><span>API Key 使用服务端密钥加密入库，浏览器和审计日志均不记录明文。</span></p></div>
          </form>
          <footer><button class="cancel" :disabled="saving" @click="closeDrawer">取消</button><button class="save" form="ai-connection-form" :disabled="saving"><LoaderCircle v-if="saving" class="spin" :size="17" /><ShieldCheck v-else :size="17" />{{ saving ? '正在保存…' : '保存连接' }}</button></footer>
        </aside>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.ai-settings{display:flex;flex-direction:column;gap:18px;color:#22372d}.settings-toolbar{display:flex;justify-content:space-between;align-items:flex-start;gap:24px}.settings-toolbar p{display:flex;align-items:center;gap:7px;margin:0 0 7px;color:#18754e;font-size:13px;font-weight:800}.settings-toolbar h2{margin:0;font-size:24px}.settings-toolbar span{display:block;margin-top:9px;color:#718078;font-size:13px}
.primary-action{height:42px;display:flex;align-items:center;gap:8px;padding:0 16px;border:0;border-radius:9px;background:#126b47;color:#fff;font-weight:800;cursor:pointer}.setting-tabs{display:flex;gap:4px;border-bottom:1px solid #dde5df}.setting-tabs button{position:relative;height:42px;padding:0 15px;border:0;background:transparent;color:#6c7972;font-weight:700;cursor:pointer}.setting-tabs button.active{color:#116c47}.setting-tabs button.active::after{content:"";position:absolute;left:12px;right:12px;bottom:-1px;height:2px;background:#167a50}.setting-tabs button:disabled{cursor:not-allowed;color:#a3aca7}.setting-tabs small{margin-left:4px;font-size:9px}
.notice{display:flex;align-items:flex-start;gap:8px;padding:11px 13px;border-radius:9px;font-size:13px}.notice.success{border:1px solid #cce6d6;background:#eef8f2;color:#146d46}.notice.error{border:1px solid #efcfcc;background:#fff1f0;color:#a93e38}.notice button{margin-left:auto;border:0;background:transparent;color:inherit;cursor:pointer}
.summary-row{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:12px}.summary-row article{display:flex;align-items:center;gap:13px;padding:17px 18px;border:1px solid #e0e6e2;border-radius:11px;background:#fff}.summary-row article>span{width:38px;height:38px;display:grid;place-items:center;border-radius:50%;background:#eaf5ef;color:#14724b}.summary-row small,.summary-row strong{display:block}.summary-row small{color:#7a867f;font-size:12px}.summary-row strong{margin-top:3px;font-size:22px}
.connection-table{overflow:hidden;border:1px solid #dde4df;border-radius:12px;background:#fff}.table-title{display:flex;align-items:center;justify-content:space-between;padding:17px 19px;border-bottom:1px solid #e5e9e6}.table-title h3{margin:0;font-size:16px}.table-title p{margin:5px 0 0;color:#7c8981;font-size:12px}.table-title button{display:flex;align-items:center;gap:6px;border:0;background:transparent;color:#4f675a;cursor:pointer}.table-scroll{overflow-x:auto}.connection-row{min-width:1060px;display:grid;grid-template-columns:1.05fr 1.55fr 1fr .72fr .85fr .8fr 1.45fr;align-items:center;gap:13px;min-height:72px;padding:0 18px;border-bottom:1px solid #e8ece9;font-size:13px}.connection-row:last-child{border:0}.table-head{min-height:42px;background:#f6f8f6;color:#6e7b74;font-size:12px;font-weight:800}.name-cell strong,.name-cell small,.provider-cell strong,.provider-cell small,.test-cell strong,.test-cell small,.updated-cell span,.updated-cell small{display:block}.name-cell small{display:flex;align-items:center;gap:4px;margin-top:6px;color:#819087;font-size:11px}.provider-cell small{max-width:250px;margin-top:5px;color:#849088;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.connection-row code{font-size:12px;color:#28523d}.status-badge{width:max-content;display:flex;align-items:center;gap:6px;padding:5px 8px;border-radius:20px;background:#f0f2f0;color:#6d7972;font-size:11px}.status-badge i{width:6px;height:6px;border-radius:50%;background:#9aa39e}.status-badge.enabled{background:#e9f6ee;color:#157249}.status-badge.enabled i{background:#1d9b61}.test-cell strong{display:flex;align-items:center;gap:5px;font-size:12px;color:#6d7872}.test-cell.success strong{color:#15734a}.test-cell.failed strong{color:#bd433d}.test-cell small,.updated-cell small{margin-top:5px;color:#8c9690;font-size:10px}.row-actions{display:flex;align-items:center;gap:4px}.row-actions button{height:32px;display:flex;align-items:center;gap:5px;padding:0 7px;border:0;border-radius:6px;background:transparent;color:#176e49;font-size:11px;cursor:pointer}.row-actions button:hover{background:#edf5f0}.row-actions .power-action{color:#5f6f66}.row-actions .power-action.on{color:#a6443f}.connection-table>footer{padding:12px 18px;background:#fafbfa;color:#849088;font-size:11px}.empty-state{min-height:240px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;color:#789086}.empty-state strong{color:#40564a}.empty-state span{font-size:12px}.empty-state button{display:flex;align-items:center;gap:6px;margin-top:5px;border:0;border-radius:8px;padding:9px 13px;background:#e9f4ee;color:#126e48;font-weight:700;cursor:pointer}
.drawer-layer{position:fixed;inset:0;z-index:100;background:rgba(18,38,28,.36);backdrop-filter:blur(1px)}.config-drawer{position:absolute;right:0;top:0;width:min(520px,100%);height:100%;display:grid;grid-template-rows:auto 1fr auto;background:#fff;box-shadow:-14px 0 40px rgba(14,45,29,.13)}.config-drawer>header{height:78px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid #e2e7e4}.config-drawer header small{color:#7b8981}.config-drawer h3{margin:5px 0 0;font-size:19px}.config-drawer header button{width:40px;height:40px;border:0;border-radius:8px;background:transparent;color:#627168;cursor:pointer}.config-drawer form{overflow-y:auto;padding:23px 24px;display:flex;flex-direction:column;gap:18px}.config-drawer form>label{display:flex;flex-direction:column;gap:7px}.config-drawer label>span{font-size:13px;font-weight:750}.config-drawer label b{color:#cf433c}.config-drawer input:not([type=range]):not([type=checkbox]),.config-drawer select,.config-drawer textarea{width:100%;height:44px;border:1px solid #d7dfda;border-radius:8px;padding:0 12px;background:#fff;color:#263b30;font:inherit;outline:none}.config-drawer textarea{height:82px;padding:10px 12px;resize:vertical}.config-drawer input:focus,.config-drawer select:focus,.config-drawer textarea:focus{border-color:#187a50;box-shadow:0 0 0 3px rgba(24,122,80,.11)}.config-drawer label small{color:#829087;font-size:11px;line-height:1.5}.config-drawer output{float:right;color:#17754e}.secret-input{position:relative}.secret-input input{padding-right:44px!important}.secret-input button{position:absolute;right:3px;top:3px;width:38px;height:38px;border:0;background:transparent;color:#75837b;cursor:pointer}.range{accent-color:#167a50}.counter{text-align:right}.default-toggle{flex-direction:row!important;align-items:center;justify-content:space-between;padding:14px;border:1px solid #e0e6e2;border-radius:9px;background:#fafbfa}.default-toggle strong,.default-toggle small{display:block}.default-toggle strong{font-size:13px}.default-toggle small{margin-top:5px}.default-toggle input{width:38px;height:21px;accent-color:#15784e}.security-callout{display:flex;gap:10px;padding:13px;border:1px solid #cce5d6;border-radius:9px;background:#eef8f2;color:#176a46}.security-callout p{margin:0}.security-callout b,.security-callout span{display:block}.security-callout b{font-size:12px}.security-callout span{margin-top:4px;color:#507365;font-size:11px;line-height:1.5}.config-drawer>footer{display:flex;justify-content:flex-end;gap:9px;padding:16px 24px;border-top:1px solid #e1e6e3;background:#fff}.config-drawer>footer button{height:42px;display:flex;align-items:center;gap:7px;padding:0 17px;border-radius:8px;font-weight:750;cursor:pointer}.cancel{border:1px solid #d4ddd7;background:#fff;color:#496055}.save{border:0;background:#126b47;color:#fff}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:900px){.settings-toolbar{flex-direction:column}.summary-row{grid-template-columns:1fr}.primary-action{width:100%;justify-content:center}.config-drawer{width:100%}}
</style>
