<script setup lang="ts">
import {
  ArrowRight, CheckCircle2, ChevronRight, CircleAlert, Clock3, Database,
  Download, FileCheck2, FlaskConical, Gauge, History, LoaderCircle, PackageCheck,
  Play, RefreshCw, Route, ShieldCheck, Sparkles, Waypoints,
} from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { downloadOperationsReport, getOperationsReadiness } from '../services/api'
import type { OperationsReadiness } from '../types/logistics'

const router = useRouter()
const data = ref<OperationsReadiness>()
const busy = ref(true)
const exporting = ref(false)
const error = ref('')
const selectedStep = ref(2)

const dimensionIcons = [Database, FlaskConical, History, ShieldCheck]
const totalDuration = computed(() => {
  const seconds = data.value?.total_duration_seconds ?? 0
  return `${Math.floor(seconds / 60)} 分 ${String(seconds % 60).padStart(2, '0')} 秒`
})

function kpiText(key: string, value: number, unit: string) {
  if (key === 'cost_saving') return `¥${value.toLocaleString('zh-CN')}`
  if (key === 'solve_time') return `${Math.round(value)}${unit}`
  return `${value.toFixed(key === 'service_rate' ? 0 : 1)}${unit}`
}

function barWidth(row: { baseline: number; optimized: number }, key: 'baseline' | 'optimized') {
  const maximum = Math.max(row.baseline, row.optimized, 1)
  return `${Math.max(4, row[key] / maximum * 100)}%`
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    data.value = await getOperationsReadiness()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '运营证据加载失败'
  } finally {
    busy.value = false
  }
}

async function exportReport() {
  exporting.value = true
  error.value = ''
  try {
    const blob = await downloadOperationsReport()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `祁智运运营成果证据报告-${new Date().toISOString().slice(0, 10)}.html`
    link.click()
    URL.revokeObjectURL(url)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '成果报告导出失败'
  } finally {
    exporting.value = false
  }
}

function openRoute(route: string) {
  router.push(route)
}

onMounted(load)
</script>

<template>
  <section class="cc-shell">
    <header class="cc-heading">
      <div>
        <h1>运营评估中心</h1>
        <p>运营证据链：数据场景 → 算法评估 → 执行闭环 → 系统保障 → 成果归档</p>
      </div>
      <div class="cc-heading-actions">
        <button class="cc-button secondary" :disabled="busy" @click="load">
          <RefreshCw :size="16" :class="{ spin: busy }" />刷新证据
        </button>
        <button class="cc-button primary" :disabled="exporting || !data" @click="exportReport">
          <LoaderCircle v-if="exporting" class="spin" :size="16" />
          <Download v-else :size="16" />导出成果报告
        </button>
      </div>
    </header>

    <div v-if="error" class="cc-alert"><CircleAlert :size="16" />{{ error }}</div>
    <div v-if="busy && !data" class="cc-loading"><LoaderCircle class="spin" />正在聚合运营证据</div>

    <template v-else-if="data">
      <section class="cc-readiness-rail">
        <div class="cc-overall">
          <span>整体就绪度</span>
          <b>{{ data.overall_score }}<small>/100</small></b>
          <em>{{ data.overall_score >= 90 ? '运营状态优秀' : data.overall_score >= 80 ? '已具备稳定运营条件' : '仍有证据需补充' }}</em>
        </div>
        <div v-for="(item, index) in data.dimensions" :key="item.key" class="cc-dimension">
          <component :is="dimensionIcons[index]" :size="22" />
          <div><span>{{ item.name }}</span><b>{{ item.score }}<small>/100</small></b></div>
          <em :class="{ attention: !item.ready }">
            <CheckCircle2 v-if="item.ready" :size="12" /><CircleAlert v-else :size="12" />
            {{ item.ready ? '已就绪' : `${item.gaps.length} 项需补充` }}
          </em>
        </div>
      </section>

      <div class="cc-grid">
        <aside class="cc-script-panel">
          <div class="cc-panel-title"><div><Play :size="17" /><b>标准作业流程</b></div><span>共 {{ totalDuration }}</span></div>
          <div class="cc-steps">
            <button
              v-for="step in data.script" :key="step.step"
              :class="{ selected: selectedStep === step.step }"
              @click="selectedStep = step.step"
            >
              <i>{{ step.step }}</i>
              <div>
                <strong>{{ step.title }}</strong>
                <p>{{ step.description }}</p>
                <span><Clock3 :size="11" />{{ step.duration_seconds }} 秒</span>
                <em v-if="!step.ready"><CircleAlert :size="11" />证据待补充</em>
                <a v-if="selectedStep === step.step" @click.stop="openRoute(step.route)">
                  进入{{ step.title }}<ArrowRight :size="13" />
                </a>
              </div>
            </button>
          </div>
        </aside>

        <main class="cc-center">
          <section class="cc-outcomes">
            <div class="cc-panel-title"><div><Sparkles :size="17" /><b>核心成果</b></div><span>全部来自最近一次有效实验</span></div>
            <div class="cc-kpis">
              <div v-for="item in data.kpis" :key="item.key">
                <span>{{ item.name }}</span>
                <b>{{ kpiText(item.key, item.value, item.unit) }}</b>
                <small>{{ item.source_id || '暂无证据编号' }}</small>
              </div>
            </div>
            <div class="cc-compare-title">
              <b>方案效果对比</b><span><i class="baseline"></i>业务基线 <i class="optimized"></i>优化方案</span>
            </div>
            <div class="cc-comparison">
              <div v-for="row in data.comparison" :key="row.key" class="cc-comparison-row">
                <span>{{ row.name }}</span>
                <div>
                  <i class="baseline" :style="{ width: barWidth(row, 'baseline') }"></i>
                  <i class="optimized" :style="{ width: barWidth(row, 'optimized') }"></i>
                </div>
                <b>{{ row.optimized.toLocaleString('zh-CN') }} {{ row.unit }}</b>
                <em v-if="row.improvement">{{ row.improvement > 0 ? '改善' : '变化' }} {{ Math.abs(row.improvement).toFixed(1) }}%</em>
              </div>
            </div>
          </section>

          <section class="cc-evidence-panel">
            <div class="cc-panel-title"><div><FileCheck2 :size="17" /><b>能力验证矩阵</b></div><span>{{ data.evidence.filter(item => item.status === 'verified').length }}/{{ data.evidence.length }} 项已验证</span></div>
            <div class="cc-evidence-table">
              <div class="cc-evidence-head"><span>要求维度</span><span>已实现能力</span><span>验证依据</span><span>状态</span></div>
              <button v-for="item in data.evidence" :key="item.requirement" @click="openRoute(item.route)">
                <strong>{{ item.requirement }}</strong>
                <span>{{ item.capability }}</span>
                <code>{{ item.evidence_id || '待补充' }}</code>
                <em :class="item.status">
                  <CheckCircle2 v-if="item.status === 'verified'" :size="13" />
                  <CircleAlert v-else :size="13" />
                  {{ item.status === 'verified' ? '已验证' : '需补充' }}
                </em>
              </button>
            </div>
          </section>
        </main>

        <aside class="cc-right">
          <section class="cc-score-panel">
            <div class="cc-panel-title"><div><Gauge :size="17" /><b>运营就绪度</b></div></div>
            <div class="cc-ring" :style="{ '--score': `${data.overall_score * 3.6}deg` }">
              <div><b>{{ data.overall_score }}</b><span>/100</span></div>
            </div>
            <div class="cc-score-list">
              <div v-for="item in data.dimensions" :key="item.key"><span>{{ item.name }}</span><b>{{ item.score }}<small>/100</small></b></div>
            </div>
          </section>

          <section class="cc-reference-panel">
            <button v-for="(item, index) in data.references" :key="item.label" @click="openRoute(item.route)">
              <component :is="[PackageCheck, FlaskConical, Route, ShieldCheck][index]" :size="19" />
              <div><span>{{ item.label }}</span><b>{{ item.value || '待补充' }}</b><small>{{ item.detail }}</small></div>
              <ChevronRight :size="15" />
            </button>
          </section>

          <section class="cc-tips">
            <div class="cc-panel-title"><div><Waypoints :size="17" /><b>运营建议</b></div></div>
            <ul><li v-for="tip in data.tips" :key="tip">{{ tip }}</li></ul>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.cc-shell{color:#253b30}.cc-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:17px}.cc-heading h1{font-size:25px;line-height:1.2;color:#152f23;margin:0}.cc-heading p{font-size:11px;color:#6f7c75;margin:7px 0 0}.cc-heading-actions{display:flex;gap:9px}.cc-button{height:40px;display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:0 15px;border:1px solid #cedad2;border-radius:8px;background:#fff;color:#315943;font-size:10px;font-weight:700;cursor:pointer}.cc-button.primary{border-color:#0f7043;background:#0f7043;color:#fff}.cc-button:disabled{opacity:.55}.cc-alert,.cc-loading{display:flex;align-items:center;gap:8px;padding:11px 14px;border-radius:9px;font-size:10px}.cc-alert{color:#a83e39;background:#fff1ef;border:1px solid #efcecb;margin-bottom:13px}.cc-loading{height:450px;justify-content:center;color:#18794b;background:#fff;border:1px solid #e0e7e2}.cc-readiness-rail{display:grid;grid-template-columns:210px repeat(4,1fr);min-height:118px;margin-bottom:14px;background:#fff;border:1px solid #dfe6e1;border-radius:12px;box-shadow:0 4px 16px rgba(21,58,39,.04)}.cc-overall,.cc-dimension{padding:18px 21px;border-right:1px solid #e4e9e6}.cc-readiness-rail>*:last-child{border:0}.cc-overall span,.cc-overall b,.cc-overall em{display:block}.cc-overall span{font-size:10px;font-weight:700;color:#52655a}.cc-overall b{font-size:37px;line-height:1;color:#147b4a;margin:8px 0 5px}.cc-overall small,.cc-dimension small,.cc-score-list small{font-size:10px;color:#7d8982;font-weight:500}.cc-overall em,.cc-dimension em{font-style:normal;font-size:9px;color:#16804d}.cc-dimension{display:grid;grid-template-columns:42px 1fr;align-items:center;column-gap:10px}.cc-dimension>svg{grid-row:1/3;width:40px;height:40px;padding:9px;color:#157b49;background:#e9f5ee;border-radius:50%}.cc-dimension span,.cc-dimension b{display:block}.cc-dimension span{font-size:10px;color:#53665b}.cc-dimension b{font-size:21px;color:#147b4a;margin-top:3px}.cc-dimension em{grid-column:2;display:flex;align-items:center;gap:4px}.cc-dimension em.attention{color:#ad730e}.cc-grid{display:grid;grid-template-columns:250px minmax(540px,1fr) 290px;gap:14px;align-items:start}.cc-script-panel,.cc-outcomes,.cc-evidence-panel,.cc-score-panel,.cc-reference-panel,.cc-tips{background:#fff;border:1px solid #dfe6e1;border-radius:11px;box-shadow:0 4px 14px rgba(21,58,39,.035)}.cc-script-panel{padding:15px}.cc-panel-title{display:flex;align-items:center;justify-content:space-between;padding-bottom:11px;border-bottom:1px solid #e7ece8}.cc-panel-title>div{display:flex;align-items:center;gap:6px;color:#213e30}.cc-panel-title b{font-size:11px}.cc-panel-title svg{color:#147b4a}.cc-panel-title>span{font-size:8px;color:#859089}.cc-steps{margin-top:7px}.cc-steps>button{position:relative;width:100%;display:grid;grid-template-columns:31px 1fr;gap:8px;padding:10px 7px;border:0;border-bottom:1px solid #ebefec;background:#fff;text-align:left;cursor:pointer}.cc-steps>button:last-child{border:0}.cc-steps>button.selected{background:#edf7f1;border:1px solid #cce3d5;border-radius:8px}.cc-steps i{width:27px;height:27px;display:grid;place-items:center;border-radius:50%;font-style:normal;font-size:11px;font-weight:800;background:#858d89;color:#fff}.cc-steps .selected i{background:#147b4a}.cc-steps strong{font-size:11px;color:#2c3f35}.cc-steps p{font-size:8px;line-height:1.5;color:#7b8880;margin:4px 0}.cc-steps span,.cc-steps em{display:flex;align-items:center;gap:4px;font-size:8px;color:#7e8983;font-style:normal}.cc-steps em{color:#ae710c;margin-top:3px}.cc-steps a{width:max-content;display:flex;align-items:center;gap:5px;margin-top:8px;padding:7px 9px;border-radius:6px;background:#147b4a;color:#fff;font-size:8px}.cc-center,.cc-right{display:flex;flex-direction:column;gap:12px}.cc-outcomes,.cc-evidence-panel{padding:15px}.cc-kpis{display:grid;grid-template-columns:repeat(4,1fr);margin:12px 0}.cc-kpis>div{padding:4px 13px;border-right:1px solid #e3e9e5}.cc-kpis>div:last-child{border:0}.cc-kpis span,.cc-kpis b,.cc-kpis small{display:block}.cc-kpis span{font-size:8px;color:#76837c}.cc-kpis b{font-size:18px;color:#137948;margin:6px 0 4px}.cc-kpis small{font:7px Consolas,monospace;color:#929b96;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cc-compare-title{display:flex;align-items:center;justify-content:space-between;margin:11px 0 7px}.cc-compare-title b{font-size:10px}.cc-compare-title span{display:flex;align-items:center;gap:5px;font-size:7px;color:#818c86}.cc-compare-title i{width:9px;height:6px;margin-left:5px}.cc-compare-title .baseline,.cc-comparison i.baseline{background:#b2b8b4}.cc-compare-title .optimized,.cc-comparison i.optimized{background:#147b4a}.cc-comparison-row{display:grid;grid-template-columns:80px minmax(150px,1fr) 85px 72px;gap:8px;align-items:center;min-height:35px}.cc-comparison-row>span{font-size:8px;color:#586a60}.cc-comparison-row>div{display:flex;flex-direction:column;gap:3px}.cc-comparison-row i{display:block;height:5px;border-radius:3px}.cc-comparison-row b{font-size:8px;color:#33483d;text-align:right}.cc-comparison-row em{font-style:normal;font-size:8px;color:#147b4a;text-align:right}.cc-evidence-table{border:1px solid #e1e7e3;border-radius:8px;overflow:hidden;margin-top:11px}.cc-evidence-head,.cc-evidence-table>button{display:grid;grid-template-columns:105px 1.4fr 145px 75px;gap:7px;align-items:center;padding:0 10px}.cc-evidence-head{height:32px;background:#f2f6f3;font-size:8px;color:#738078;font-weight:700}.cc-evidence-table>button{width:100%;min-height:40px;border:0;border-top:1px solid #e6ebe8;background:#fff;text-align:left;cursor:pointer}.cc-evidence-table>button:hover{background:#f3f8f5}.cc-evidence-table strong{font-size:8px;color:#2c4939}.cc-evidence-table span{font-size:8px;line-height:1.45;color:#68776f}.cc-evidence-table code{font-size:8px;color:#36604a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cc-evidence-table em{display:flex;align-items:center;gap:4px;font-style:normal;font-size:8px}.cc-evidence-table em.verified{color:#137a49}.cc-evidence-table em.attention{color:#ad720d}.cc-score-panel{padding:15px}.cc-ring{--score:0deg;width:128px;height:128px;display:grid;place-items:center;border-radius:50%;margin:15px auto;background:conic-gradient(#147b4a var(--score),#e3ece6 0);position:relative}.cc-ring:after{content:"";position:absolute;inset:13px;border-radius:50%;background:#fff}.cc-ring>div{position:relative;z-index:1;text-align:center}.cc-ring b,.cc-ring span{display:block}.cc-ring b{font-size:34px;color:#123c28}.cc-ring span{font-size:9px;color:#829087}.cc-score-list{border-top:1px solid #e7ece8;padding-top:8px}.cc-score-list>div{display:flex;align-items:center;justify-content:space-between;padding:5px 2px}.cc-score-list span{font-size:8px;color:#5d6e64}.cc-score-list b{font-size:11px;color:#147b4a}.cc-reference-panel{overflow:hidden}.cc-reference-panel>button{width:100%;display:grid;grid-template-columns:25px 1fr 16px;gap:7px;align-items:center;padding:11px 12px;border:0;border-bottom:1px solid #e5eae7;background:#fff;text-align:left;cursor:pointer}.cc-reference-panel>button:last-child{border:0}.cc-reference-panel>button:hover{background:#f2f7f4}.cc-reference-panel svg{color:#147b4a}.cc-reference-panel span,.cc-reference-panel b,.cc-reference-panel small{display:block}.cc-reference-panel span{font-size:8px;color:#78857e}.cc-reference-panel b{font:700 9px Consolas,monospace;color:#264735;margin:3px 0}.cc-reference-panel small{font-size:7px;color:#89938d;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cc-tips{padding:15px}.cc-tips ul{margin:10px 0 0;padding-left:15px}.cc-tips li{font-size:8px;color:#65766c;line-height:1.6;margin:5px 0}.cc-tips li::marker{color:#147b4a}.spin{animation:cc-spin 1s linear infinite}@keyframes cc-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.spin{animation:none}}
.cc-shell{max-width:1680px;margin:0 auto;color:#20372b}.cc-heading{margin-bottom:18px}.cc-heading h1{font-size:28px;letter-spacing:-.5px}.cc-heading p{font-size:12px;line-height:1.55}.cc-button{height:42px;padding:0 17px;font-size:11px;border-radius:9px;box-shadow:none}.cc-readiness-rail{min-height:108px;margin-bottom:16px;border-color:#dce5df;box-shadow:0 8px 24px rgba(22,55,38,.035)}.cc-overall,.cc-dimension{padding:16px 20px}.cc-overall span,.cc-dimension span{font-size:11px}.cc-overall b{font-size:38px}.cc-overall em,.cc-dimension em{font-size:10px}.cc-dimension{grid-template-columns:46px 1fr;column-gap:12px}.cc-dimension>svg{width:42px;height:42px}.cc-dimension b{font-size:23px}.cc-grid{grid-template-columns:260px minmax(0,1fr) 300px;gap:16px;width:100%;align-items:start}.cc-script-panel,.cc-outcomes,.cc-evidence-panel,.cc-score-panel,.cc-reference-panel,.cc-tips{border-color:#dce5df;box-shadow:0 8px 24px rgba(22,55,38,.035)}.cc-script-panel,.cc-outcomes,.cc-evidence-panel,.cc-score-panel,.cc-tips{padding:17px}.cc-panel-title b{font-size:13px}.cc-panel-title>span{font-size:9px}.cc-steps>button{grid-template-columns:34px 1fr;gap:10px;padding:12px 8px}.cc-steps i{width:29px;height:29px;font-size:12px}.cc-steps strong{font-size:12px}.cc-steps p{font-size:9px;line-height:1.6}.cc-steps span,.cc-steps em,.cc-steps a{font-size:9px}.cc-kpis{margin:14px 0}.cc-kpis span{font-size:9px}.cc-kpis b{font-size:21px}.cc-kpis small{font-size:8px}.cc-compare-title b{font-size:11px}.cc-compare-title span{font-size:9px}.cc-comparison-row{min-height:38px}.cc-comparison-row>span,.cc-comparison-row>b,.cc-comparison-row>em{font-size:9px}.cc-evidence-head,.cc-evidence-table>button{font-size:9px}.cc-evidence-table>button{min-height:45px}.cc-score-list span{font-size:9px}.cc-reference-panel span{font-size:9px}.cc-reference-panel b{font-size:10px}.cc-reference-panel small,.cc-tips li{font-size:8px}.cc-ring{width:122px;height:122px}
@media(max-width:1250px){.cc-grid{grid-template-columns:235px minmax(0,1fr)}.cc-right{grid-column:1/-1;display:grid;grid-template-columns:240px 1fr 1fr}.cc-readiness-rail{grid-template-columns:190px repeat(4,1fr)}}
@media(max-width:760px){.cc-heading{align-items:flex-start;gap:14px}.cc-heading,.cc-heading-actions{flex-direction:column}.cc-heading-actions,.cc-heading-actions .cc-button{width:100%}.cc-readiness-rail{grid-template-columns:1fr 1fr}.cc-overall{grid-column:1/-1}.cc-readiness-rail>*{border-right:1px solid #e4e9e6;border-bottom:1px solid #e4e9e6}.cc-grid{grid-template-columns:1fr}.cc-right{grid-column:auto;display:flex}.cc-kpis{grid-template-columns:1fr 1fr}.cc-kpis>div:nth-child(2){border-right:0}.cc-kpis>div{padding:9px}.cc-comparison-row{grid-template-columns:65px 1fr 65px}.cc-comparison-row em{grid-column:2/-1}.cc-evidence-head{display:none}.cc-evidence-table>button{grid-template-columns:100px 1fr;padding:9px}.cc-evidence-table code,.cc-evidence-table em{grid-column:2}.cc-score-panel{display:grid;grid-template-columns:1fr 1fr;align-items:center}.cc-score-panel>.cc-panel-title{grid-column:1/-1}.cc-ring{width:112px;height:112px}.cc-ring b{font-size:29px}}
</style>
