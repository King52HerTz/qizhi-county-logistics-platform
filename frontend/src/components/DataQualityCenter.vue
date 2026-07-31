<script setup lang="ts">
import {
  AlertCircle, AlertTriangle, ArrowLeft, Check, CheckCircle2, CircleOff,
  Download, FileSpreadsheet, LoaderCircle, LockKeyhole, RefreshCw, Settings2,
  ShieldCheck, UploadCloud, X,
} from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  commitDataImportBatch, downloadDataImportErrors, downloadOrderImportTemplate,
  getDataImportBatches, getDataQualityReport, getSessionRole, previewOrderImport,
  publishMasterData, updateDataQualityRule,
} from '../services/api'
import type {
  DataImportBatch, DataQualityReport, DataQualityRule,
} from '../types/logistics'

const emit = defineEmits<{ changed: [] }>()
const route = useRoute()
const router = useRouter()
const report = ref<DataQualityReport>({
  items: [], blocked_count: 0, warning_count: 0, publish_ready: false,
})
const batches = ref<DataImportBatch[]>([])
const loading = ref(true)
const ruleSaving = ref<number>()
const publishing = ref(false)
const drawerOpen = ref(false)
const uploadStep = ref<1 | 2 | 3>(1)
const selectedFile = ref<File>()
const preview = ref<DataImportBatch>()
const previewing = ref(false)
const committing = ref(false)
const dragging = ref(false)
const scenarioName = ref(`祁东县 ${new Date().getFullYear()} 黄花菜城乡配送场景`)
const activateAfterPublish = ref(false)
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const isAdmin = computed(() => getSessionRole() === 'admin')

const statusMeta = {
  passed: { label: '通过', icon: CheckCircle2 },
  warning: { label: '警告', icon: AlertTriangle },
  blocked: { label: '阻断', icon: AlertCircle },
  disabled: { label: '已停用', icon: CircleOff },
} as const
const batchStatus = {
  validated: '预检通过',
  rejected: '校验失败',
  committed: '导入成功',
} as const

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}
function saveBlob(blob: Blob, filename: string) {
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(href)
}
async function load() {
  loading.value = true
  try {
    const [quality, imports] = await Promise.all([
      getDataQualityReport(), getDataImportBatches(),
    ])
    report.value = quality
    batches.value = imports.items
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '数据质量信息读取失败' }
  } finally {
    loading.value = false
  }
}
function openImport() {
  drawerOpen.value = true
  uploadStep.value = 1
  selectedFile.value = undefined
  preview.value = undefined
}
function closeImport() {
  if (previewing.value || (committing.value && uploadStep.value !== 3)) return
  drawerOpen.value = false
  router.replace({ query: {} })
}
function chooseFile(files: FileList | null) {
  const file = files?.[0]
  if (!file) return
  if (!/\.(xlsx|csv)$/i.test(file.name)) {
    notice.value = { kind: 'error', text: '请选择 .xlsx 或 UTF-8 CSV 文件' }
    return
  }
  selectedFile.value = file
}
function drop(event: DragEvent) {
  dragging.value = false
  chooseFile(event.dataTransfer?.files ?? null)
}
async function downloadTemplate() {
  try {
    saveBlob(await downloadOrderImportTemplate(), '祁智运订单导入模板.xlsx')
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '模板下载失败' }
  }
}
async function runPreview() {
  if (!selectedFile.value || previewing.value) return
  previewing.value = true
  try {
    preview.value = await previewOrderImport(selectedFile.value)
    uploadStep.value = 2
    await load()
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '文件预检失败' }
  } finally {
    previewing.value = false
  }
}
async function downloadErrors(item: DataImportBatch) {
  try {
    saveBlob(await downloadDataImportErrors(item.id), `${item.batch_code}-错误回执.csv`)
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '错误回执下载失败' }
  }
}
async function commitImport() {
  if (!preview.value || preview.value.error_rows || committing.value) return
  committing.value = true
  try {
    preview.value = await commitDataImportBatch(preview.value.id)
    uploadStep.value = 3
    notice.value = {
      kind: 'success',
      text: `批次 ${preview.value.batch_code} 已整体入库 ${preview.value.valid_rows} 条订单`,
    }
    emit('changed')
    await load()
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '订单入库失败' }
  } finally {
    committing.value = false
  }
}
async function saveRule(rule: DataQualityRule, input?: { enabled?: boolean; severity?: 'error' | 'warning' }) {
  if (!isAdmin.value || ruleSaving.value) return
  ruleSaving.value = rule.id
  try {
    await updateDataQualityRule(rule.id, {
      enabled: input?.enabled ?? rule.enabled,
      severity: input?.severity ?? rule.severity,
    })
    notice.value = { kind: 'success', text: `规则“${rule.name}”已更新` }
    await load()
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '规则更新失败' }
  } finally {
    ruleSaving.value = undefined
  }
}
async function publish() {
  if (!isAdmin.value || !report.value.publish_ready || !scenarioName.value.trim() || publishing.value) return
  publishing.value = true
  try {
    const result = await publishMasterData(scenarioName.value.trim(), activateAfterPublish.value)
    notice.value = {
      kind: 'success',
      text: `${result.scenario.version_key} 已生成${result.scenario.status === 'active' ? '并激活' : '为草稿'}`,
    }
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '场景发布失败' }
  } finally {
    publishing.value = false
  }
}

onMounted(async () => {
  await load()
  if (route.query.import === '1') openImport()
})
</script>

<template>
  <div class="quality-workspace">
    <div v-if="notice" :class="['master-notice', notice.kind]">
      <Check v-if="notice.kind === 'success'" :size="17" />
      <AlertCircle v-else :size="17" />
      {{ notice.text }}
      <button aria-label="关闭提示" @click="notice = undefined"><X :size="15" /></button>
    </div>

    <div class="quality-main-grid">
      <section class="quality-checks">
        <header>
          <div><h2>发布就绪检查</h2><p>发布前自动复核订单、运力、网点和冷链约束</p></div>
          <button class="quality-icon-button" title="重新检查" @click="load">
            <LoaderCircle v-if="loading" class="master-spin" :size="17" />
            <RefreshCw v-else :size="17" />
          </button>
        </header>
        <div class="quality-rule-head">
          <span>校验规则</span><span>严重性</span><span>状态</span><span>检查结果</span><span>启用</span>
        </div>
        <div v-if="loading" class="master-empty">
          <LoaderCircle class="master-spin" :size="26" /><span>正在执行质量检查</span>
        </div>
        <div
          v-for="rule in report.items"
          v-else
          :key="rule.id"
          class="quality-rule-row"
        >
          <div><strong>{{ rule.name }}</strong><small>{{ rule.description }}</small></div>
          <select
            :value="rule.severity"
            :disabled="!isAdmin || ruleSaving === rule.id"
            aria-label="规则严重级别"
            @change="saveRule(rule, { severity: ($event.target as HTMLSelectElement).value as 'error' | 'warning' })"
          >
            <option value="error">阻断</option>
            <option value="warning">警告</option>
          </select>
          <span :class="['quality-rule-state', rule.status]">
            <component :is="statusMeta[rule.status].icon" :size="15" />
            {{ statusMeta[rule.status].label }}
          </span>
          <span class="quality-detail">{{ rule.detail }}</span>
          <label class="quality-mini-switch" :title="isAdmin ? '启用或停用规则' : '仅管理员可修改'">
            <input
              type="checkbox"
              :checked="rule.enabled"
              :disabled="!isAdmin || ruleSaving === rule.id"
              @change="saveRule(rule, { enabled: ($event.target as HTMLInputElement).checked })"
            >
            <i />
          </label>
        </div>
      </section>

      <aside class="quality-publish">
        <header><ShieldCheck :size="20" /><h2>发布为调度场景</h2></header>
        <label><span>场景名称 <b>*</b></span><input v-model="scenarioName" maxlength="120"></label>
        <label class="publish-switch">
          <span><strong>发布后立即激活</strong><small>原激活场景将自动归档</small></span>
          <input v-model="activateAfterPublish" type="checkbox">
        </label>
        <div :class="['publish-readiness', report.publish_ready ? 'ready' : 'blocked']">
          <CheckCircle2 v-if="report.publish_ready" :size="17" />
          <LockKeyhole v-else :size="17" />
          <span>
            <b>{{ report.publish_ready ? '已具备发布条件' : `${report.blocked_count} 项阻断问题待处理` }}</b>
            <small v-if="report.warning_count">{{ report.warning_count }} 项警告不会阻断发布</small>
          </span>
        </div>
        <button
          class="master-primary publish-button"
          :disabled="!isAdmin || !report.publish_ready || !scenarioName.trim() || publishing"
          @click="publish"
        >
          <LoaderCircle v-if="publishing" class="master-spin" :size="16" />
          <ShieldCheck v-else :size="16" />
          {{ publishing ? '正在生成' : '生成场景版本' }}
        </button>
        <small v-if="!isAdmin" class="quality-admin-hint">仅管理员可以发布场景和修改规则</small>
      </aside>
    </div>

    <section class="quality-imports">
      <header>
        <div><h2>最近导入批次</h2><p>保留文件预检和确认入库结果，便于追踪与复核</p></div>
        <button class="master-primary" @click="openImport"><UploadCloud :size="16" />批量导入订单</button>
      </header>
      <div class="quality-import-scroll">
        <div class="quality-import-row head">
          <span>文件名称</span><span>批次号</span><span>总行数</span><span>有效</span>
          <span>错误</span><span>状态</span><span>操作人</span><span>导入时间</span><span>操作</span>
        </div>
        <div v-for="item in batches" :key="item.id" class="quality-import-row">
          <div><FileSpreadsheet :size="16" /><span><strong>{{ item.filename }}</strong><small>{{ item.import_type === 'orders' ? '订单数据' : item.import_type }}</small></span></div>
          <code>{{ item.batch_code }}</code>
          <span>{{ item.total_rows }}</span><span class="green-number">{{ item.valid_rows }}</span>
          <span :class="{ 'red-number': item.error_rows }">{{ item.error_rows }}</span>
          <span :class="['batch-state', item.status]"><i />{{ batchStatus[item.status] }}</span>
          <span>{{ item.committed_by || item.created_by || '—' }}</span>
          <span>{{ formatTime(item.created_at) }}</span>
          <button v-if="item.error_rows" @click="downloadErrors(item)"><Download :size="14" />错误回执</button>
          <span v-else class="muted-action">—</span>
        </div>
        <div v-if="!loading && !batches.length" class="master-empty">
          <FileSpreadsheet :size="28" /><span>尚无导入批次</span>
        </div>
      </div>
    </section>
  </div>

  <div v-if="drawerOpen" class="master-drawer-layer" @click.self="closeImport">
    <aside class="master-drawer import-drawer" role="dialog" aria-modal="true" aria-label="批量导入订单">
      <header>
        <div><small>订单台账</small><h2>批量导入订单</h2></div>
        <button class="master-close" aria-label="关闭" @click="closeImport"><X :size="21" /></button>
      </header>
      <div class="import-drawer-body">
        <ol class="import-steps">
          <li :class="{ active: uploadStep === 1, done: uploadStep > 1 }"><b>1</b><span>上传文件</span></li>
          <li :class="{ active: uploadStep === 2, done: uploadStep > 2 }"><b>2</b><span>数据预检</span></li>
          <li :class="{ active: uploadStep === 3 }"><b>3</b><span>确认入库</span></li>
        </ol>

        <template v-if="uploadStep === 1">
          <div
            :class="['import-dropzone', { dragging }]"
            @dragenter.prevent="dragging = true"
            @dragover.prevent
            @dragleave.prevent="dragging = false"
            @drop.prevent="drop"
          >
            <UploadCloud :size="35" />
            <strong>拖拽文件到此处，或选择文件</strong>
            <span>支持 .xlsx 与 UTF-8 CSV，单个文件不超过 5 MB</span>
            <label><input type="file" accept=".xlsx,.csv" @change="chooseFile(($event.target as HTMLInputElement).files)">选择文件</label>
          </div>
          <div v-if="selectedFile" class="import-selected-file">
            <FileSpreadsheet :size="24" />
            <span><strong>{{ selectedFile.name }}</strong><small>{{ (selectedFile.size / 1024).toFixed(1) }} KB</small></span>
            <button aria-label="移除文件" @click="selectedFile = undefined"><X :size="16" /></button>
          </div>
          <button class="import-template-link" @click="downloadTemplate"><Download :size="15" />下载订单导入模板</button>
          <div class="import-tip"><Settings2 :size="17" /><span><b>导入说明</b>订单编号不可重复；服务网点必须已启用；时间窗支持 HH:MM 或分钟数。</span></div>
        </template>

        <template v-else-if="uploadStep === 2 && preview">
          <div class="import-file-summary">
            <FileSpreadsheet :size="26" />
            <span><strong>{{ preview.filename }}</strong><small>批次 {{ preview.batch_code }}</small></span>
          </div>
          <section class="import-preview-summary">
            <h3>预检结果</h3>
            <div>
              <span><b>{{ preview.total_rows }}</b><small>总行数</small></span>
              <span><b class="green-number">{{ preview.valid_rows }}</b><small>有效行数</small></span>
              <span><b class="red-number">{{ preview.error_rows }}</b><small>错误行数</small></span>
              <span><b>{{ preview.warning_rows }}</b><small>警告行数</small></span>
            </div>
          </section>
          <section v-if="preview.errors.length" class="import-errors">
            <header><h3>错误明细（共 {{ preview.errors.length }} 条）</h3><button @click="downloadErrors(preview)"><Download :size="14" />下载错误回执</button></header>
            <div class="import-error-head"><span>行号</span><span>错误字段</span><span>错误说明</span></div>
            <div v-for="(item, index) in preview.errors" :key="`${item.row}-${index}`" class="import-error-row">
              <span>{{ item.row ? `第 ${item.row} 行` : '文件' }}</span><strong>{{ item.field }}</strong><span>{{ item.message }}</span>
            </div>
          </section>
          <div v-else class="import-pass"><CheckCircle2 :size="22" /><span><b>文件预检通过</b><small>{{ preview.valid_rows }} 条订单可以整体入库</small></span></div>
        </template>

        <div v-else class="import-complete">
          <span><Check :size="30" /></span>
          <h3>订单导入完成</h3>
          <p>{{ preview?.valid_rows }} 条订单已写入正式台账，操作记录已进入审计中心。</p>
        </div>
      </div>
      <footer>
        <template v-if="uploadStep === 1">
          <button class="master-cancel" @click="closeImport">取消</button>
          <button class="master-save" :disabled="!selectedFile || previewing" @click="runPreview">
            <LoaderCircle v-if="previewing" class="master-spin" :size="16" /><UploadCloud v-else :size="16" />
            {{ previewing ? '正在预检' : '上传并预检' }}
          </button>
        </template>
        <template v-else-if="uploadStep === 2">
          <button class="master-cancel" @click="uploadStep = 1"><ArrowLeft :size="16" />返回上传</button>
          <button class="master-save" :disabled="Boolean(preview?.error_rows) || committing" @click="commitImport">
            <LoaderCircle v-if="committing" class="master-spin" :size="16" /><LockKeyhole v-else :size="16" />
            {{ committing ? '正在入库' : '确认导入' }}
          </button>
        </template>
        <button v-else class="master-save" @click="closeImport"><Check :size="16" />完成</button>
      </footer>
    </aside>
  </div>
</template>
