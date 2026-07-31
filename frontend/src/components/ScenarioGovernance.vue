<script setup lang="ts">
import {
  ArchiveRestore, ArrowLeftRight, CheckCircle2, ChevronRight, CircleDot,
  Clock3, Download, FileDiff, FileSpreadsheet, GitCompareArrows, History,
  LoaderCircle, PackageCheck, RefreshCw, Search, Send, ShieldCheck, UploadCloud,
  X, XCircle,
} from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import {
  approveScenarioReview, compareScenarioVersions, downloadScenarioTemplate,
  getScenarioVersionDetail, getScenarioVersions, rejectScenarioReview,
  rollbackScenarioVersion, submitScenarioReview, uploadScenario,
} from '../services/api'
import type {
  ScenarioCompareResponse, ScenarioDiffGroup, ScenarioGovernanceSummary,
  ScenarioVersionDetail, ScenarioVersionStatus, ScenarioVersionView,
} from '../types/logistics'

const emit = defineEmits<{ activated: [] }>()
const versions = ref<ScenarioVersionView[]>([])
const summary = ref<ScenarioGovernanceSummary>({
  total: 0, active: 0, pending_review: 0, draft: 0, rejected: 0, archived: 0,
})
const selected = ref<ScenarioVersionDetail>()
const busy = ref(false)
const detailBusy = ref(false)
const actionBusy = ref(false)
const error = ref('')
const message = ref('')
const search = ref('')
const statusFilter = ref('')
const actionNote = ref('')
const importOpen = ref(false)
const diffOpen = ref(false)
const selectedFile = ref<File>()
const baseId = ref<number>()
const targetId = ref<number>()
const comparison = ref<ScenarioCompareResponse>()

const statusMeta: Record<ScenarioVersionStatus, { label: string; hint: string }> = {
  draft: { label: '草稿', hint: '可补充发布说明并提交审核' },
  pending_review: { label: '待审核', hint: '等待管理员复核运力与订单约束' },
  rejected: { label: '已驳回', hint: '根据审核意见修改后可再次提交' },
  active: { label: '当前生效', hint: '调度计算正在使用这个场景版本' },
  archived: { label: '已归档', hint: '历史版本，可执行受控回滚' },
}

const actionTitle = computed(() => {
  if (!selected.value) return ''
  if (selected.value.status === 'pending_review') return '审核处置'
  if (selected.value.status === 'archived') return '版本回滚'
  if (['draft', 'rejected'].includes(selected.value.status)) return '提交发布审核'
  return '当前发布状态'
})

const diffGroups = computed(() => comparison.value
  ? [
      { key: 'nodes', label: '节点', data: comparison.value.nodes },
      { key: 'orders', label: '订单', data: comparison.value.orders },
      { key: 'vehicles', label: '车辆', data: comparison.value.vehicles },
    ]
  : [])

function formatTime(value?: string) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function statusLabel(status: ScenarioVersionStatus) {
  return statusMeta[status]?.label ?? status
}

function setDefaultNote(item: ScenarioVersionView) {
  if (item.status === 'pending_review') actionNote.value = '运力、订单、时间窗及冷链约束复核通过'
  else if (item.status === 'archived') actionNote.value = '恢复该稳定版本，处理当前生产场景异常'
  else actionNote.value = `发布 ${item.version_key}：完成业务数据校验与调度约束确认`
}

async function loadVersions(keepSelection = true) {
  busy.value = true
  error.value = ''
  try {
    const result = await getScenarioVersions({
      search: search.value.trim() || undefined,
      status: statusFilter.value || undefined,
    })
    versions.value = result.items
    summary.value = result.summary
    const next = keepSelection
      ? versions.value.find(item => item.id === selected.value?.id) ?? versions.value[0]
      : versions.value[0]
    if (next) await selectVersion(next)
    else selected.value = undefined
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '场景版本加载失败'
  } finally {
    busy.value = false
  }
}

async function selectVersion(item: ScenarioVersionView) {
  detailBusy.value = true
  error.value = ''
  try {
    selected.value = await getScenarioVersionDetail(item.id)
    setDefaultNote(item)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '版本详情加载失败'
  } finally {
    detailBusy.value = false
  }
}

async function runAction(action: 'submit' | 'approve' | 'reject' | 'rollback') {
  if (!selected.value || actionNote.value.trim().length < 2) {
    error.value = '请填写至少 2 个字的操作说明'
    return
  }
  actionBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const handlers = {
      submit: submitScenarioReview,
      approve: approveScenarioReview,
      reject: rejectScenarioReview,
      rollback: rollbackScenarioVersion,
    }
    await handlers[action](selected.value.id, actionNote.value.trim())
    message.value = {
      submit: '版本已提交审核',
      approve: '审核通过，新版本已发布',
      reject: '版本已驳回并记录审核意见',
      rollback: '历史版本已回滚并重新生效',
    }[action]
    if (action === 'approve' || action === 'rollback') emit('activated')
    await loadVersions()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '版本操作失败'
  } finally {
    actionBusy.value = false
  }
}

async function openComparison() {
  if (versions.value.length < 2) {
    error.value = '至少需要两个场景版本才能进行对比'
    return
  }
  const active = versions.value.find(item => item.status === 'active')
  targetId.value = selected.value?.id ?? versions.value[0].id
  baseId.value = active?.id !== targetId.value
    ? active?.id
    : versions.value.find(item => item.id !== targetId.value)?.id
  diffOpen.value = true
  await loadComparison()
}

async function loadComparison() {
  if (!baseId.value || !targetId.value || baseId.value === targetId.value) {
    comparison.value = undefined
    return
  }
  detailBusy.value = true
  error.value = ''
  try {
    comparison.value = await compareScenarioVersions(baseId.value, targetId.value)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '版本差异加载失败'
  } finally {
    detailBusy.value = false
  }
}

async function swapComparison() {
  const current = baseId.value
  baseId.value = targetId.value
  targetId.value = current
  await loadComparison()
}

async function importVersion() {
  if (!selectedFile.value) return
  actionBusy.value = true
  error.value = ''
  try {
    const result = await uploadScenario(selectedFile.value)
    message.value = `${result.scenario.version_key} 已导入为草稿`
    importOpen.value = false
    selectedFile.value = undefined
    await loadVersions(false)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '场景导入失败'
  } finally {
    actionBusy.value = false
  }
}

async function downloadTemplate() {
  try {
    const blob = await downloadScenarioTemplate()
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = '祁智运场景导入模板.xlsx'
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '模板下载失败'
  }
}

function delta(value: number) {
  return value > 0 ? `+${value}` : String(value)
}

function groupTotal(group: ScenarioDiffGroup) {
  return group.added + group.removed + group.changed
}

onMounted(() => loadVersions(false))
</script>

<template>
  <section class="sg-shell">
    <div class="sg-toolbar">
      <div>
        <span class="sg-kicker"><ShieldCheck :size="14" /> 版本发布控制台</span>
        <h2>场景版本治理</h2>
        <p>所有生产场景先审核、再发布，可追溯每次变更并安全回滚。</p>
      </div>
      <div class="sg-toolbar-actions">
        <button class="sg-button ghost" @click="openComparison">
          <GitCompareArrows :size="16" />版本对比
        </button>
        <button class="sg-button primary" @click="importOpen = true">
          <UploadCloud :size="16" />导入新版本
        </button>
      </div>
    </div>

    <div class="sg-summary">
      <div><PackageCheck /><span>当前生效</span><b>{{ summary.active }}</b><small>生产调度版本</small></div>
      <div><Clock3 /><span>待审核</span><b>{{ summary.pending_review }}</b><small>需要管理员处理</small></div>
      <div><FileSpreadsheet /><span>草稿 / 驳回</span><b>{{ summary.draft + summary.rejected }}</b><small>等待完善后提交</small></div>
      <div><History /><span>版本总数</span><b>{{ summary.total }}</b><small>{{ summary.archived }} 个历史归档</small></div>
    </div>

    <p v-if="error" class="sg-alert error"><XCircle :size="15" />{{ error }}</p>
    <p v-else-if="message" class="sg-alert success"><CheckCircle2 :size="15" />{{ message }}</p>

    <div class="sg-workspace">
      <div class="sg-list-panel">
        <div class="sg-list-tools">
          <label class="sg-search">
            <Search :size="15" />
            <input v-model="search" placeholder="搜索名称、版本号或县域" @keyup.enter="loadVersions(false)">
          </label>
          <select v-model="statusFilter" aria-label="版本状态筛选" @change="loadVersions(false)">
            <option value="">全部状态</option>
            <option v-for="(meta, key) in statusMeta" :key="key" :value="key">{{ meta.label }}</option>
          </select>
          <button class="sg-icon-button" title="刷新" :disabled="busy" @click="loadVersions()">
            <RefreshCw :size="15" :class="{ spin: busy }" />
          </button>
        </div>

        <div class="sg-table">
          <div class="sg-table-head">
            <span>版本 / 场景</span><span>业务数据</span><span>状态</span><span>更新时间</span><span></span>
          </div>
          <button
            v-for="item in versions" :key="item.id"
            class="sg-row" :class="{ selected: selected?.id === item.id }"
            @click="selectVersion(item)"
          >
            <span class="sg-version">
              <b>{{ item.version_key }}</b>
              <small>{{ item.name }} · {{ item.county_name }}</small>
            </span>
            <span class="sg-data">
              <b>{{ item.node_count }}</b> 节点 · <b>{{ item.order_count }}</b> 单 · <b>{{ item.vehicle_count }}</b> 车
            </span>
            <span class="sg-status" :class="item.status"><i></i>{{ statusLabel(item.status) }}</span>
            <span class="sg-time">{{ formatTime(item.reviewed_at || item.submitted_at || item.created_at) }}</span>
            <ChevronRight :size="16" />
          </button>
          <div v-if="!versions.length && !busy" class="sg-empty">没有符合条件的场景版本</div>
        </div>
      </div>

      <aside class="sg-detail">
        <div v-if="detailBusy" class="sg-detail-loading"><LoaderCircle class="spin" />正在读取版本详情</div>
        <template v-else-if="selected">
          <div class="sg-detail-head">
            <div>
              <span class="sg-status" :class="selected.status"><i></i>{{ statusLabel(selected.status) }}</span>
              <h3>{{ selected.version_key }}</h3>
              <p>{{ statusMeta[selected.status].hint }}</p>
            </div>
            <button class="sg-icon-button" title="与其他版本对比" @click="openComparison"><FileDiff :size="17" /></button>
          </div>

          <div class="sg-detail-metrics">
            <div><span>订单量</span><b>{{ selected.order_count }}</b></div>
            <div><span>车辆数</span><b>{{ selected.vehicle_count }}</b></div>
            <div><span>节点数</span><b>{{ selected.node_count }}</b></div>
          </div>

          <dl class="sg-meta">
            <div><dt>创建人</dt><dd>{{ selected.created_by || '系统' }}</dd></div>
            <div><dt>来源</dt><dd>{{ selected.source_filename || '系统内置数据' }}</dd></div>
            <div><dt>提交人</dt><dd>{{ selected.submitted_by || '—' }}</dd></div>
            <div><dt>审核人</dt><dd>{{ selected.reviewed_by || '—' }}</dd></div>
            <div class="wide"><dt>数据指纹</dt><dd class="fingerprint">{{ selected.fingerprint || '—' }}</dd></div>
          </dl>

          <div class="sg-action-card">
            <div><CircleDot :size="15" /><b>{{ actionTitle }}</b></div>
            <textarea
              v-if="selected.status !== 'active'"
              v-model="actionNote" rows="3" maxlength="500"
              :placeholder="selected.status === 'pending_review' ? '填写审核结论' : '填写发布或回滚说明'"
            ></textarea>
            <p v-else>{{ selected.review_note || selected.release_note || '该版本已完成审核并处于生产生效状态。' }}</p>
            <div v-if="selected.status === 'pending_review'" class="sg-action-buttons">
              <button class="sg-button danger" :disabled="actionBusy" @click="runAction('reject')"><X :size="15" />驳回</button>
              <button class="sg-button primary" :disabled="actionBusy" @click="runAction('approve')"><CheckCircle2 :size="15" />通过并发布</button>
            </div>
            <button
              v-else-if="selected.status === 'draft' || selected.status === 'rejected'"
              class="sg-button primary full" :disabled="actionBusy" @click="runAction('submit')"
            ><Send :size="15" />提交审核</button>
            <button
              v-else-if="selected.status === 'archived'"
              class="sg-button amber full" :disabled="actionBusy" @click="runAction('rollback')"
            ><ArchiveRestore :size="15" />确认回滚至此版本</button>
          </div>

          <div class="sg-timeline">
            <div class="sg-section-title"><History :size="15" /><b>版本轨迹</b><span>{{ selected.transitions.length }} 条记录</span></div>
            <div v-for="item in selected.transitions" :key="item.id" class="sg-event">
              <i></i>
              <div>
                <b>{{ item.from_status ? `${statusLabel(item.from_status)} → ` : '' }}{{ statusLabel(item.to_status) }}</b>
                <p>{{ item.note || '系统状态变更' }}</p>
                <small>{{ item.actor || '系统' }} · {{ formatTime(item.created_at) }}</small>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="sg-empty">请选择一个版本查看详情</div>
      </aside>
    </div>

    <div v-if="importOpen" class="sg-overlay" @click.self="importOpen = false">
      <aside class="sg-drawer narrow">
        <header><div><span class="sg-kicker">Excel 场景入库</span><h2>导入新版本</h2></div><button @click="importOpen = false"><X /></button></header>
        <p class="sg-drawer-copy">导入后仅生成草稿，不会直接影响当前生产调度。通过审核后才会生效。</p>
        <button class="sg-template" @click="downloadTemplate"><Download :size="17" /><span><b>下载标准导入模板</b><small>包含节点、订单、车辆和元数据工作表</small></span></button>
        <label class="sg-dropzone">
          <UploadCloud :size="28" />
          <b>{{ selectedFile?.name || '选择 .xlsx 场景文件' }}</b>
          <span>系统将校验关联关系、时间窗、容量和必填字段</span>
          <input type="file" accept=".xlsx" @change="selectedFile = ($event.target as HTMLInputElement).files?.[0]">
        </label>
        <button class="sg-button primary full" :disabled="!selectedFile || actionBusy" @click="importVersion">
          <LoaderCircle v-if="actionBusy" class="spin" :size="16" /><UploadCloud v-else :size="16" />校验并导入草稿
        </button>
      </aside>
    </div>

    <div v-if="diffOpen" class="sg-overlay" @click.self="diffOpen = false">
      <aside class="sg-drawer diff">
        <header><div><span class="sg-kicker"><ArrowLeftRight :size="14" /> 版本差异</span><h2>场景版本对比</h2></div><button @click="diffOpen = false"><X /></button></header>
        <div class="sg-compare-selectors">
          <label><span>基准版本</span><select v-model="baseId" @change="loadComparison"><option v-for="item in versions" :key="item.id" :value="item.id">{{ item.version_key }} · {{ statusLabel(item.status) }}</option></select></label>
          <button title="交换基准与目标" @click="swapComparison"><ArrowLeftRight :size="17" /></button>
          <label><span>目标版本</span><select v-model="targetId" @change="loadComparison"><option v-for="item in versions" :key="item.id" :value="item.id">{{ item.version_key }} · {{ statusLabel(item.status) }}</option></select></label>
        </div>
        <template v-if="comparison">
          <div class="sg-deltas">
            <div><span>节点变化</span><b :class="{ positive: comparison.deltas.node_count > 0 }">{{ delta(comparison.deltas.node_count) }}</b></div>
            <div><span>订单变化</span><b :class="{ positive: comparison.deltas.order_count > 0 }">{{ delta(comparison.deltas.order_count) }}</b></div>
            <div><span>车辆变化</span><b :class="{ positive: comparison.deltas.vehicle_count > 0 }">{{ delta(comparison.deltas.vehicle_count) }}</b></div>
            <div><span>总货量</span><b :class="{ positive: comparison.deltas.total_weight_kg > 0 }">{{ delta(comparison.deltas.total_weight_kg) }} kg</b></div>
          </div>
          <div v-for="group in diffGroups" :key="group.key" class="sg-diff-group">
            <div class="sg-section-title"><FileDiff :size="15" /><b>{{ group.label }}明细</b><span>{{ groupTotal(group.data) }} 项变化</span></div>
            <div class="sg-change-counts">
              <span class="added">新增 {{ group.data.added }}</span>
              <span class="removed">删除 {{ group.data.removed }}</span>
              <span class="changed">修改 {{ group.data.changed }}</span>
            </div>
            <div v-if="group.data.details.length" class="sg-change-list">
              <div v-for="item in group.data.details" :key="`${item.change_type}-${item.object_id}`">
                <span :class="item.change_type">{{ { added: '新增', removed: '删除', changed: '修改' }[item.change_type] }}</span>
                <b>{{ item.object_id }}</b><p>{{ item.description }}</p>
              </div>
            </div>
            <p v-else class="sg-no-change">两个版本的{{ group.label }}数据一致</p>
          </div>
        </template>
        <div v-else class="sg-empty">请选择两个不同版本查看差异</div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.sg-shell{display:flex;flex-direction:column;gap:14px;color:#263a30}.sg-toolbar,.sg-summary,.sg-list-panel,.sg-detail{background:#fff;border:1px solid #e1e8e3;border-radius:14px;box-shadow:0 5px 18px rgba(18,58,37,.04)}.sg-toolbar{display:flex;justify-content:space-between;align-items:center;padding:18px 20px}.sg-toolbar h2,.sg-drawer h2{font-size:18px;margin:3px 0 2px;color:#123b28}.sg-toolbar p,.sg-drawer-copy{font-size:10px;color:#78867e;margin:0;line-height:1.7}.sg-kicker{display:flex;align-items:center;gap:5px;font-size:9px;font-weight:800;color:#1a8050;letter-spacing:.5px}.sg-toolbar-actions,.sg-action-buttons{display:flex;gap:8px}.sg-button{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid #d2dfd6;border-radius:8px;padding:9px 13px;background:#fff;color:#345b46;font-size:10px;font-weight:700;cursor:pointer}.sg-button:hover{background:#f2f7f4}.sg-button.primary{border-color:#167849;background:#167849;color:#fff}.sg-button.danger{border-color:#efcbc8;color:#b74640;background:#fff8f7}.sg-button.amber{border-color:#e2a326;background:#e2a326;color:#153b29}.sg-button.full{width:100%;margin-top:9px}.sg-button:disabled{opacity:.55;cursor:not-allowed}.sg-summary{display:grid;grid-template-columns:repeat(4,1fr);overflow:hidden}.sg-summary>div{display:grid;grid-template-columns:auto 1fr;column-gap:11px;align-items:center;padding:16px 19px;border-right:1px solid #e7ece8}.sg-summary>div:last-child{border:0}.sg-summary svg{grid-row:1/4;color:#17804f;background:#e8f4ed;padding:8px;width:36px;height:36px;border-radius:10px}.sg-summary span,.sg-summary small{font-size:9px;color:#849088}.sg-summary b{font-size:22px;color:#163d2a;line-height:1.1}.sg-summary small{font-size:8px}.sg-alert{display:flex;align-items:center;gap:7px;margin:0;padding:9px 12px;border-radius:8px;font-size:10px}.sg-alert.error{color:#a73e38;background:#fff1ef;border:1px solid #f0d0cd}.sg-alert.success{color:#176c43;background:#e8f5ed;border:1px solid #cce8d6}.sg-workspace{display:grid;grid-template-columns:minmax(650px,1fr) 355px;gap:14px;align-items:start}.sg-list-panel{padding:15px}.sg-list-tools{display:grid;grid-template-columns:minmax(220px,1fr) 135px 36px;gap:8px;margin-bottom:12px}.sg-search{height:36px;display:flex;align-items:center;gap:7px;border:1px solid #dce4de;border-radius:8px;padding:0 10px;color:#819087;background:#fbfcfb}.sg-search input{border:0;outline:0;background:transparent;width:100%;font-size:10px;color:#263b30}.sg-list-tools select,.sg-compare-selectors select{border:1px solid #dce4de;border-radius:8px;padding:0 9px;background:#fbfcfb;color:#40554a;font-size:10px;outline:0}.sg-icon-button,.sg-drawer header>button,.sg-compare-selectors>button{width:36px;height:36px;display:grid;place-items:center;border:1px solid #dce4de;border-radius:8px;background:#fff;color:#3d6951;cursor:pointer}.sg-table{border:1px solid #e4ebe6;border-radius:10px;overflow:hidden}.sg-table-head,.sg-row{display:grid;grid-template-columns:minmax(205px,1.35fr) 180px 84px 86px 18px;gap:9px;align-items:center;padding:0 13px}.sg-table-head{min-height:36px;background:#f4f7f5;color:#839088;font-size:9px;font-weight:700}.sg-row{width:100%;min-height:70px;border:0;border-top:1px solid #ebefec;background:#fff;text-align:left;color:#53645a;cursor:pointer}.sg-row:hover,.sg-row.selected{background:#f1f8f4}.sg-row.selected{box-shadow:inset 3px 0 #1b8050}.sg-version b,.sg-version small{display:block}.sg-version b{font:700 11px Consolas,monospace;color:#195d3c}.sg-version small{font-size:8px;color:#89938d;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sg-data{font-size:9px;color:#77857d}.sg-data b{color:#244c36}.sg-status{display:inline-flex;align-items:center;gap:6px;font-size:9px;color:#69776f}.sg-status i{width:7px;height:7px;border-radius:50%;background:#9ca6a0}.sg-status.active{color:#147949;font-weight:800}.sg-status.active i{background:#24a568;box-shadow:0 0 0 3px #ddf2e6}.sg-status.pending_review{color:#ae710d}.sg-status.pending_review i{background:#e9a923}.sg-status.rejected{color:#b34640}.sg-status.rejected i{background:#d95b53}.sg-status.draft i{background:#7f99a9}.sg-time{font-size:8px;color:#8a948e}.sg-detail{padding:17px;position:sticky;top:72px}.sg-detail-head{display:flex;align-items:flex-start;justify-content:space-between;padding-bottom:14px;border-bottom:1px solid #e8ede9}.sg-detail-head h3{font:800 17px Consolas,monospace;color:#153d29;margin:10px 0 4px}.sg-detail-head p{font-size:9px;color:#829087;margin:0;line-height:1.5}.sg-detail-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:13px 0}.sg-detail-metrics>div{padding:9px;background:#f4f7f5;border-radius:8px}.sg-detail-metrics span,.sg-detail-metrics b{display:block}.sg-detail-metrics span{font-size:8px;color:#849087}.sg-detail-metrics b{margin-top:3px;font-size:16px;color:#17422c}.sg-meta{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:0 0 14px}.sg-meta>div{min-width:0}.sg-meta .wide{grid-column:1/-1}.sg-meta dt{font-size:8px;color:#8a958e}.sg-meta dd{font-size:9px;color:#3b5145;margin:3px 0 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sg-meta .fingerprint{font-family:Consolas,monospace;color:#27704b}.sg-action-card{padding:12px;border:1px solid #dfe8e2;border-radius:10px;background:#f8faf8}.sg-action-card>div:first-child,.sg-section-title{display:flex;align-items:center;gap:6px;color:#1d6844;font-size:10px}.sg-action-card textarea{width:100%;resize:vertical;border:1px solid #d9e3dc;border-radius:8px;padding:9px;margin:9px 0 0;outline:0;font:10px/1.6 inherit;color:#344b3e}.sg-action-card textarea:focus{border-color:#279061;box-shadow:0 0 0 3px #e7f4ec}.sg-action-card>p{font-size:9px;line-height:1.7;color:#65736b;margin:8px 0 0}.sg-action-buttons{justify-content:flex-end;margin-top:8px}.sg-timeline{margin-top:16px}.sg-section-title{padding-bottom:9px;border-bottom:1px solid #e8ede9}.sg-section-title span{margin-left:auto;color:#8b958f;font-size:8px;font-weight:400}.sg-event{display:grid;grid-template-columns:10px 1fr;gap:8px;padding:10px 0;border-bottom:1px solid #eef1ef}.sg-event:last-child{border:0}.sg-event>i{width:8px;height:8px;margin-top:3px;border-radius:50%;background:#2a925f;box-shadow:0 0 0 3px #e4f2e9}.sg-event b{font-size:9px;color:#355044}.sg-event p{font-size:8px;line-height:1.55;color:#697970;margin:3px 0}.sg-event small{font-size:7px;color:#96a09a}.sg-empty,.sg-detail-loading{padding:42px 15px;text-align:center;color:#849089;font-size:10px}.sg-detail-loading{display:flex;align-items:center;justify-content:center;gap:7px}.sg-overlay{position:fixed;inset:0;background:rgba(7,31,21,.38);backdrop-filter:blur(2px);z-index:100;display:flex;justify-content:flex-end}.sg-drawer{height:100%;width:min(680px,92vw);padding:24px;background:#f6f8f6;box-shadow:-15px 0 40px rgba(5,37,22,.18);overflow:auto}.sg-drawer.narrow{width:min(430px,92vw);background:#fff}.sg-drawer header{display:flex;align-items:flex-start;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid #dfe6e1}.sg-drawer h2{font-size:20px;margin-top:6px}.sg-drawer-copy{margin:18px 0}.sg-template{width:100%;display:flex;gap:10px;align-items:center;text-align:left;border:1px solid #d9e6dc;border-radius:10px;padding:12px;background:#f1f8f3;color:#236344;cursor:pointer}.sg-template span,.sg-template b,.sg-template small{display:block}.sg-template b{font-size:10px}.sg-template small{font-size:8px;color:#749080;margin-top:4px}.sg-dropzone{height:185px;margin:14px 0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;border:1px dashed #90b39d;border-radius:12px;background:#f8faf8;color:#2e7650;cursor:pointer}.sg-dropzone b{font-size:11px}.sg-dropzone span{font-size:8px;color:#819087}.sg-dropzone input{display:none}.sg-compare-selectors{display:grid;grid-template-columns:1fr 36px 1fr;gap:9px;align-items:end;margin:17px 0}.sg-compare-selectors label{display:flex;flex-direction:column;gap:6px}.sg-compare-selectors label>span{font-size:9px;color:#708078;font-weight:700}.sg-compare-selectors select{height:38px}.sg-deltas{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:13px}.sg-deltas>div{padding:12px;border:1px solid #e0e7e2;border-radius:10px;background:#fff}.sg-deltas span,.sg-deltas b{display:block}.sg-deltas span{font-size:8px;color:#819087}.sg-deltas b{font-size:17px;margin-top:5px;color:#314d3e}.sg-deltas b.positive{color:#17804f}.sg-diff-group{padding:14px;margin-top:10px;border:1px solid #e0e7e2;border-radius:11px;background:#fff}.sg-change-counts{display:flex;gap:6px;margin:10px 0}.sg-change-counts span,.sg-change-list span{padding:3px 7px;border-radius:12px;font-size:8px}.added{color:#16794a;background:#e7f5ec}.removed{color:#b54740;background:#fcebea}.changed{color:#a66b0c;background:#fff3d8}.sg-change-list>div{display:grid;grid-template-columns:42px 105px 1fr;gap:7px;align-items:start;padding:8px 0;border-top:1px solid #edf1ee}.sg-change-list b{font:700 9px Consolas,monospace;color:#335443}.sg-change-list p,.sg-no-change{font-size:8px;color:#748179;line-height:1.55;margin:0}.sg-no-change{padding:10px;text-align:center;background:#f6f8f6;border-radius:8px}.spin{animation:sg-spin 1s linear infinite}@keyframes sg-spin{to{transform:rotate(360deg)}}
@media(max-width:1100px){.sg-workspace{grid-template-columns:1fr}.sg-detail{position:static}.sg-summary{grid-template-columns:repeat(2,1fr)}.sg-summary>div:nth-child(2){border-right:0}.sg-summary>div:nth-child(-n+2){border-bottom:1px solid #e7ece8}}
@media(max-width:760px){.sg-toolbar{align-items:flex-start;gap:14px}.sg-toolbar,.sg-toolbar-actions{flex-direction:column}.sg-toolbar-actions,.sg-toolbar-actions .sg-button{width:100%}.sg-summary{grid-template-columns:1fr 1fr}.sg-summary>div{padding:12px}.sg-table-head{display:none}.sg-row{grid-template-columns:1fr auto;gap:6px;padding:11px;min-height:0}.sg-row>.sg-data,.sg-row>.sg-time{grid-column:1}.sg-row>.sg-status{grid-column:2;grid-row:1}.sg-row>svg{display:none}.sg-list-tools{grid-template-columns:1fr 105px 36px}.sg-compare-selectors{grid-template-columns:1fr 34px 1fr}.sg-deltas{grid-template-columns:1fr 1fr}.sg-change-list>div{grid-template-columns:42px 1fr}.sg-change-list p{grid-column:1/-1}.sg-drawer{padding:18px}}
</style>
