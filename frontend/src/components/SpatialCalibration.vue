<script setup lang="ts">
import {
  AlertCircle, CheckCircle2, Clock3, Crosshair, History, LocateFixed, MapPin,
  RefreshCw, Search, ShieldCheck,
} from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  calibrateNodeCoordinate, getMapRuntime, getMasterNodes,
  getNodeCoordinateRevisions, getSpatialQuality,
} from '../services/api'
import { loadAmap, loadAmapPlugin } from '../services/amap'
import type {
  MasterNode, MapRuntimeConfig, NodeCoordinateRevision, SpatialQualitySummary,
} from '../types/logistics'

type StatusFilter = 'review' | 'verified' | 'all'

const host = ref<HTMLDivElement>()
const nodes = ref<MasterNode[]>([])
const quality = ref<SpatialQualitySummary>({
  total: 0, verified: 0, needs_review: 0, unverified: 0, outside_bounds: 0,
  duplicate: 0, missing_address: 0, display_coordinate_system: 'GCJ-02',
  storage_coordinate_system: 'WGS-84',
})
const revisions = ref<NodeCoordinateRevision[]>([])
const selectedId = ref('')
const search = ref('')
const filter = ref<StatusFilter>('review')
const loading = ref(true)
const saving = ref(false)
const relocating = ref(false)
const mapOnline = ref(false)
const notice = ref('')
const error = ref('')
const draftLongitude = ref(112.08)
const draftLatitude = ref(26.78)
const draftAddress = ref('')
const draftAccuracy = ref<number | undefined>()
const note = ref('')

let amap: any
let markers: any[] = []
let selectedMarker: any
let boundaryOverlays: any[] = []

const selected = computed(() => nodes.value.find(node => node.id === selectedId.value))
const reviewCount = computed(() => quality.value.needs_review + quality.value.unverified)
const filteredNodes = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return nodes.value.filter((node) => {
    const statusMatches = filter.value === 'all'
      || (filter.value === 'verified' && node.coordinate_status === 'verified')
      || (filter.value === 'review' && node.coordinate_status !== 'verified')
    const textMatches = !keyword
      || `${node.id} ${node.name} ${node.address ?? ''}`.toLowerCase().includes(keyword)
    return statusMatches && textMatches
  })
})
const shiftDistance = computed(() => {
  if (!selected.value) return 0
  return haversine(
    selected.value.longitude, selected.value.latitude,
    draftLongitude.value, draftLatitude.value,
  )
})
const offlineDraftPosition = computed(() => ({
  left: `${(draftLongitude.value - 111.52) / (112.36 - 111.52) * 100}%`,
  top: `${(27.09 - draftLatitude.value) / (27.09 - 26.44) * 100}%`,
}))
const statusName = (status: MasterNode['coordinate_status']) => ({
  verified: '已核验', needs_review: '待复核', unverified: '未核验',
}[status])
const sourceName = (source: MasterNode['coordinate_source']) => ({
  seed: '初始数据', imported: '批量导入', geocoded: '高德地理编码', manual: '人工选点',
}[source])
const issueName = (node: MasterNode) =>
  node.spatial_issue === 'outside_bounds' ? '范围异常' : statusName(node.coordinate_status)

function haversine(lng1: number, lat1: number, lng2: number, lat2: number) {
  const radius = 6371008.8
  const rad = (value: number) => value * Math.PI / 180
  const dLat = rad(lat2 - lat1)
  const dLng = rad(lng2 - lng1)
  const value = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLng / 2) ** 2
  return radius * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value))
}

function formatDistance(value: number) {
  return value >= 1000 ? `${(value / 1000).toFixed(2)} km` : `${value.toFixed(1)} m`
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function markerClass(node: MasterNode, active = false) {
  const state = node.spatial_issue === 'outside_bounds'
    ? 'danger'
    : node.coordinate_status === 'verified' ? 'verified' : 'review'
  return `calibration-map-marker ${state}${active ? ' active' : ''}`
}

function markerContent(node: MasterNode, active = false) {
  return `<button class="${markerClass(node, active)}" aria-label="${node.name}">
    <span></span></button>`
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [nodeResult, qualityResult] = await Promise.all([
      getMasterNodes('limit=100'), getSpatialQuality(),
    ])
    nodes.value = nodeResult.items
    quality.value = qualityResult
    if (!selectedId.value || !nodes.value.some(node => node.id === selectedId.value)) {
      selectedId.value = nodes.value.find(node => node.coordinate_status !== 'verified')?.id
        ?? nodes.value[0]?.id ?? ''
    }
    await nextTick()
    drawMap()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '空间数据读取失败'
  } finally {
    loading.value = false
  }
}

async function selectNode(id: string, center = true) {
  selectedId.value = id
  const node = selected.value
  if (!node) return
  draftLongitude.value = node.longitude
  draftLatitude.value = node.latitude
  draftAddress.value = node.address ?? ''
  draftAccuracy.value = node.coordinate_accuracy_m
  note.value = ''
  revisions.value = []
  relocating.value = false
  try {
    revisions.value = (await getNodeCoordinateRevisions(id)).items
  } catch {
    revisions.value = []
  }
  drawMarkers()
  if (center && amap) amap.setZoomAndCenter(13, [node.longitude, node.latitude])
}

function setDraft(longitude: number, latitude: number) {
  draftLongitude.value = Number(longitude.toFixed(6))
  draftLatitude.value = Number(latitude.toFixed(6))
  draftAccuracy.value = 10
  positionSelectedMarker()
  void reverseGeocode(longitude, latitude)
}

async function reverseGeocode(longitude: number, latitude: number) {
  if (!window.AMap) return
  try {
    await loadAmapPlugin('AMap.Geocoder')
    const geocoder = new window.AMap.Geocoder({ city: '衡阳市', radius: 500 })
    geocoder.getAddress([longitude, latitude], (status: string, result: any) => {
      if (status === 'complete' && result.regeocode?.formattedAddress) {
        draftAddress.value = result.regeocode.formattedAddress
      }
    })
  } catch {
    // Coordinate picking remains available when reverse geocoding is unavailable.
  }
}

function drawMarkers() {
  if (!amap || !window.AMap) return
  markers.forEach(marker => amap.remove(marker))
  markers = nodes.value.map((node) => {
    const marker = new window.AMap.Marker({
      position: [node.longitude, node.latitude],
      content: markerContent(node, node.id === selectedId.value),
      offset: new window.AMap.Pixel(-12, -24),
      zIndex: node.id === selectedId.value ? 130 : 90,
    })
    marker.on('click', () => selectNode(node.id, false))
    amap.add(marker)
    return marker
  })
  positionSelectedMarker()
}

function positionSelectedMarker() {
  if (!amap || !window.AMap) return
  if (selectedMarker) amap.remove(selectedMarker)
  if (!relocating.value) {
    selectedMarker = undefined
    return
  }
  selectedMarker = new window.AMap.Marker({
    position: [draftLongitude.value, draftLatitude.value],
    content: '<div class="calibration-draft-marker"><span></span></div>',
    offset: new window.AMap.Pixel(-15, -30),
    zIndex: 180,
  })
  amap.add(selectedMarker)
}

function drawMap() {
  if (!amap) return
  drawMarkers()
}

function fitAll() {
  if (amap && [...boundaryOverlays, ...markers].length) {
    amap.setFitView([...boundaryOverlays, ...markers], false, [28, 28, 28, 28], 11)
  }
}

function offlineClick(event: MouseEvent) {
  if (!relocating.value) return
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const longitude = 111.52 + (event.clientX - rect.left) / rect.width * (112.36 - 111.52)
  const latitude = 27.09 - (event.clientY - rect.top) / rect.height * (27.09 - 26.44)
  setDraft(longitude, latitude)
}

function offlinePosition(node: MasterNode) {
  return {
    left: `${(node.longitude - 111.52) / (112.36 - 111.52) * 100}%`,
    top: `${(27.09 - node.latitude) / (27.09 - 26.44) * 100}%`,
  }
}

function beginRelocate() {
  relocating.value = true
  notice.value = '请在地图上点击网点的真实位置'
  positionSelectedMarker()
}

async function saveCalibration() {
  const node = selected.value
  if (!node || saving.value) return
  saving.value = true
  error.value = ''
  try {
    await calibrateNodeCoordinate(node.id, {
      longitude: draftLongitude.value,
      latitude: draftLatitude.value,
      address: draftAddress.value || undefined,
      coordinate_source: 'manual',
      coordinate_accuracy_m: draftAccuracy.value,
      coordinate_status: 'verified',
      note: note.value || '地图人工核验',
    })
    notice.value = `${node.name} 的位置已保存并标记为已核验`
    relocating.value = false
    await loadData()
    await selectNode(node.id, false)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '坐标保存失败'
  } finally {
    saving.value = false
  }
}

async function initializeMap() {
  try {
    const runtime = await getMapRuntime()
    if (runtime.mode !== 'online' || runtime.provider !== 'amap' || !runtime.web_key) return
    await loadAmap(runtime as MapRuntimeConfig)
    await nextTick()
    amap = new window.AMap.Map(host.value, {
      zoom: 10.4,
      center: [112.08, 26.78],
      viewMode: '2D',
      mapStyle: `amap://styles/${runtime.map_style}`,
      showLabel: true,
    })
    const geoData = await (await fetch('/qidong.json')).json()
    boundaryOverlays = geoData.features.flatMap((feature: any) => {
      const coordinates = feature.geometry.type === 'MultiPolygon'
        ? feature.geometry.coordinates.flat()
        : feature.geometry.coordinates
      return coordinates.map((path: number[][]) => new window.AMap.Polygon({
        path, strokeColor: '#168653', strokeWeight: 2, strokeOpacity: .9,
        fillColor: '#eaf3ed', fillOpacity: .08, zIndex: 40, bubble: true,
      }))
    })
    amap.add(boundaryOverlays)
    amap.on('click', (event: any) => {
      if (relocating.value) setDraft(event.lnglat.getLng(), event.lnglat.getLat())
    })
    mapOnline.value = true
    drawMarkers()
    fitAll()
  } catch {
    mapOnline.value = false
    error.value = '高德地图暂不可用，已切换为县域坐标校准底图'
  }
}

watch(relocating, positionSelectedMarker)
onMounted(async () => {
  await loadData()
  await initializeMap()
  if (selectedId.value) await selectNode(selectedId.value, false)
})
onBeforeUnmount(() => {
  amap?.destroy()
  amap = undefined
})
</script>

<template>
  <section class="spatial-calibration">
    <div v-if="error" class="spatial-message error"><AlertCircle :size="16" />{{ error }}</div>
    <div v-else-if="notice" class="spatial-message success"><CheckCircle2 :size="16" />{{ notice }}</div>

    <div class="spatial-summary">
      <article><MapPin :size="20" /><div><small>网点总数</small><strong>{{ quality.total }}</strong></div></article>
      <article><ShieldCheck :size="20" /><div><small>已核验</small><strong>{{ quality.verified }}</strong></div></article>
      <article class="amber"><Clock3 :size="20" /><div><small>待复核</small><strong>{{ reviewCount }}</strong></div></article>
      <article class="red"><AlertCircle :size="20" /><div><small>范围异常</small><strong>{{ quality.outside_bounds }}</strong></div></article>
    </div>

    <div class="spatial-workspace">
      <aside class="spatial-node-rail">
        <label class="spatial-search"><Search :size="16" /><input v-model="search" placeholder="搜索网点名称或编号" /></label>
        <div class="spatial-filters">
          <button :class="{ active: filter === 'review' }" @click="filter = 'review'">待复核</button>
          <button :class="{ active: filter === 'verified' }" @click="filter = 'verified'">已核验</button>
          <button :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
        </div>
        <div class="spatial-list-count">共 {{ filteredNodes.length }} 个网点</div>
        <div class="spatial-node-list">
          <button
            v-for="node in filteredNodes" :key="node.id"
            :class="{ selected: node.id === selectedId }" @click="selectNode(node.id)"
          >
            <span class="node-pin" :class="node.spatial_issue === 'outside_bounds' ? 'danger' : node.coordinate_status"></span>
            <span><strong>{{ node.name }}</strong><small>{{ node.id }}</small></span>
            <em :class="node.spatial_issue === 'outside_bounds' ? 'danger' : node.coordinate_status">{{ issueName(node) }}</em>
          </button>
          <div v-if="!filteredNodes.length" class="spatial-empty">没有符合条件的网点</div>
        </div>
      </aside>

      <div class="spatial-map-panel">
        <div class="spatial-map-toolbar">
          <button @click="fitAll"><Crosshair :size="16" />适应范围</button>
          <span>{{ mapOnline ? '高德道路地图' : '县域坐标底图' }}</span>
        </div>
        <div ref="host" class="spatial-amap" :class="{ visible: mapOnline }"></div>
        <div v-if="!mapOnline" class="spatial-offline-map" @click="offlineClick">
          <div class="county-outline"></div>
          <span class="county-name">祁东县</span>
          <button
            v-for="node in nodes" :key="node.id"
            class="offline-marker" :class="markerClass(node, node.id === selectedId)"
            :style="offlinePosition(node)" @click.stop="selectNode(node.id)"
            :aria-label="node.name"
          ><span></span></button>
          <div
            v-if="relocating" class="offline-draft"
            :style="offlineDraftPosition"
          ><span></span></div>
        </div>
        <div class="spatial-crs">展示 GCJ-02 · 存储 WGS-84</div>
        <div v-if="relocating" class="spatial-map-hint"><LocateFixed :size="16" />点击地图更新网点位置</div>
      </div>

      <aside v-if="selected" class="spatial-inspector">
        <header>
          <div><h2>{{ selected.name }}</h2><small>{{ selected.id }} · {{ sourceName(selected.coordinate_source) }}</small></div>
          <span :class="selected.spatial_issue === 'outside_bounds' ? 'danger' : selected.coordinate_status">{{ issueName(selected) }}</span>
        </header>
        <div class="spatial-form">
          <label><span>当前坐标（GCJ-02）</span><div class="coordinate-inputs"><input v-model.number="draftLongitude" type="number" step=".000001" /><input v-model.number="draftLatitude" type="number" step=".000001" /></div></label>
          <label><span>详细地址</span><textarea v-model.trim="draftAddress" rows="2" /></label>
          <div class="spatial-meta">
            <span><small>坐标来源</small><strong>{{ relocating ? '人工选点' : sourceName(selected.coordinate_source) }}</strong></span>
            <span><small>定位精度</small><strong>{{ draftAccuracy ? `± ${draftAccuracy} m` : '未登记' }}</strong></span>
            <span><small>偏移距离</small><strong>{{ formatDistance(shiftDistance) }}</strong></span>
            <span><small>存储坐标</small><strong>{{ selected.wgs84_longitude ? 'WGS-84 已生成' : '保存后生成' }}</strong></span>
          </div>
          <label><span>校准说明</span><input v-model.trim="note" placeholder="选填，记录本次核验依据" /></label>
        </div>
        <section class="spatial-history">
          <h3><History :size="15" />校准记录</h3>
          <ol v-if="revisions.length">
            <li v-for="item in revisions" :key="item.id">
              <i></i><div><strong>{{ item.coordinate_status === 'verified' ? '完成坐标核验' : '更新网点坐标' }}</strong>
              <span>{{ formatTime(item.created_at) }} · {{ item.actor_username || '系统' }}</span>
              <small>{{ item.note || `${item.longitude.toFixed(6)}, ${item.latitude.toFixed(6)}` }}</small></div>
            </li>
          </ol>
          <div v-else class="spatial-no-history">暂无校准记录</div>
        </section>
        <footer>
          <button class="secondary" :disabled="saving" @click="beginRelocate"><RefreshCw :size="16" />重新定位</button>
          <button class="primary" :disabled="saving" @click="saveCalibration"><ShieldCheck :size="16" />{{ saving ? '正在保存' : '保存并标记已核验' }}</button>
        </footer>
      </aside>
      <div v-else class="spatial-inspector empty">请选择一个网点</div>
    </div>
    <div v-if="loading" class="spatial-loading">正在读取空间数据…</div>
  </section>
</template>

<style scoped>
.spatial-calibration{position:relative;display:flex;flex-direction:column;gap:12px;color:#263b30}
.spatial-message{display:flex;align-items:center;gap:7px;padding:9px 12px;border-radius:7px;font-size:12px}.spatial-message.success{background:#edf7f1;color:#146d48}.spatial-message.error{background:#fff1ef;color:#af3f39}
.spatial-summary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #dfe5e1;border-radius:8px;background:#fff}.spatial-summary article{min-height:70px;display:flex;align-items:center;gap:12px;padding:12px 20px;border-right:1px solid #e4e9e6;color:#178454}.spatial-summary article:last-child{border:0}.spatial-summary article.amber{color:#d88913}.spatial-summary article.red{color:#d4423b}.spatial-summary small,.spatial-summary strong{display:block}.spatial-summary small{color:#75827a;font-size:11px}.spatial-summary strong{margin-top:3px;font-size:21px}
.spatial-workspace{height:clamp(630px,calc(100vh - 286px),790px);min-height:630px;display:grid;grid-template-columns:250px minmax(430px,1fr) 330px;border:1px solid #dce3df;border-radius:8px;background:#fff;overflow:hidden}
.spatial-node-rail{display:flex;min-width:0;flex-direction:column;border-right:1px solid #dfe5e1}.spatial-search{position:relative;margin:12px}.spatial-search svg{position:absolute;left:10px;top:10px;color:#78867e}.spatial-search input{width:100%;height:36px;border:1px solid #d6ded9;border-radius:6px;padding:0 10px 0 34px;font:500 12px/1 inherit;outline:none}.spatial-search input:focus{border-color:#168653;box-shadow:0 0 0 3px rgba(22,134,83,.1)}
.spatial-filters{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;padding:0 12px 10px}.spatial-filters button{height:31px;border:1px solid #d8e0db;border-radius:5px;background:#fff;color:#627168;font:700 11px/1 inherit;cursor:pointer}.spatial-filters button.active{border-color:#168653;background:#edf7f1;color:#13734a}.spatial-list-count{padding:8px 13px;background:#f7f9f7;color:#748179;font-size:10px}
.spatial-node-list{min-height:0;overflow-y:auto}.spatial-node-list>button{width:100%;min-height:61px;display:grid;grid-template-columns:27px minmax(0,1fr) auto;align-items:center;gap:7px;border:0;border-bottom:1px solid #e8ece9;background:#fff;padding:9px 11px;text-align:left;cursor:pointer}.spatial-node-list>button:hover{background:#fafcfb}.spatial-node-list>button.selected{box-shadow:inset 3px 0 #168653;background:#f0f8f4}.spatial-node-list strong,.spatial-node-list small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.spatial-node-list strong{font-size:11px}.spatial-node-list small{margin-top:4px;color:#869189;font-size:9px}.spatial-node-list em{font-style:normal;font-size:9px;color:#c07a15}.spatial-node-list em.verified{color:#168653}.spatial-node-list em.danger{color:#d4423b}.node-pin{width:19px;height:24px;position:relative;display:block;border-radius:11px 11px 11px 2px;background:#d99017;transform:rotate(-45deg)}.node-pin::after{content:"";position:absolute;width:6px;height:6px;left:6px;top:6px;border-radius:50%;background:#fff}.node-pin.verified{background:#168653}.node-pin.danger{background:#d4423b}.spatial-empty{padding:35px 12px;text-align:center;color:#849088;font-size:11px}
.spatial-map-panel{position:relative;min-width:0;background:#eef3ef;overflow:hidden}.spatial-amap{position:absolute;inset:0;visibility:hidden}.spatial-amap.visible{visibility:visible}.spatial-map-toolbar{position:absolute;z-index:10;left:12px;top:12px;display:flex;align-items:center;gap:8px}.spatial-map-toolbar button,.spatial-map-toolbar span{height:34px;display:flex;align-items:center;gap:6px;border:1px solid #d6ded9;border-radius:6px;background:rgba(255,255,255,.96);padding:0 10px;color:#42574c;font:700 10px/1 inherit}.spatial-map-toolbar button{cursor:pointer}.spatial-map-toolbar span{color:#75837b}
.spatial-offline-map{position:absolute;inset:0;overflow:hidden;background-color:#f7faf8;background-image:linear-gradient(#e3ebe6 1px,transparent 1px),linear-gradient(90deg,#e3ebe6 1px,transparent 1px),radial-gradient(circle at 50% 50%,#fff 0,#edf4ef 72%);background-size:34px 34px,34px 34px,100% 100%;cursor:crosshair}.county-outline{position:absolute;left:18%;right:17%;top:10%;bottom:10%;border:2px dashed #168653;border-radius:48% 42% 47% 38%/42% 48% 40% 51%;background:rgba(22,134,83,.035);transform:rotate(-3deg)}.county-name{position:absolute;left:51%;top:47%;transform:translate(-50%,-50%);color:#315b45;font-size:28px;font-weight:800;opacity:.36}
.offline-marker,.offline-draft{position:absolute;z-index:3;width:24px;height:24px;transform:translate(-50%,-100%);border:0;background:transparent;padding:0}.offline-marker>span,.calibration-map-marker span{display:block;width:18px;height:18px;border:3px solid #fff;border-radius:50% 50% 50% 4px;background:#d99017;box-shadow:0 1px 4px rgba(26,62,42,.28);transform:rotate(-45deg)}.offline-marker.verified>span,.calibration-map-marker.verified span{background:#168653}.offline-marker.danger>span,.calibration-map-marker.danger span{background:#d4423b}.offline-marker.active>span,.calibration-map-marker.active span{width:24px;height:24px;box-shadow:0 0 0 5px rgba(22,134,83,.2),0 2px 6px rgba(20,55,36,.3)}.offline-draft>span,.calibration-draft-marker span{display:block;width:25px;height:25px;border:4px solid #fff;border-radius:50% 50% 50% 4px;background:#2772c5;box-shadow:0 0 0 6px rgba(39,114,197,.2);transform:rotate(-45deg)}
.spatial-crs{position:absolute;z-index:10;right:12px;top:12px;padding:7px 9px;border:1px solid #dbe2de;border-radius:5px;background:rgba(255,255,255,.95);color:#6e7d75;font-size:9px}.spatial-map-hint{position:absolute;z-index:10;left:50%;bottom:18px;transform:translateX(-50%);display:flex;align-items:center;gap:6px;padding:9px 12px;border-radius:6px;background:#193d2d;color:#fff;font-size:11px;box-shadow:0 5px 14px rgba(10,42,27,.2)}
.spatial-inspector{min-width:0;display:grid;grid-template-rows:auto auto minmax(0,1fr) auto;border-left:1px solid #dfe5e1;background:#fff}.spatial-inspector>header{min-height:69px;display:flex;align-items:flex-start;justify-content:space-between;gap:8px;padding:14px;border-bottom:1px solid #e4e9e6}.spatial-inspector h2{margin:0;font-size:15px}.spatial-inspector header small{display:block;margin-top:5px;color:#7d8982;font-size:9px}.spatial-inspector header>span{padding:4px 7px;border-radius:4px;background:#fff3df;color:#bd7311;font-size:9px}.spatial-inspector header>span.verified{background:#edf7f1;color:#14734a}.spatial-inspector header>span.danger{background:#fff0ef;color:#c53f38}
.spatial-form{display:flex;flex-direction:column;gap:12px;padding:13px 14px;border-bottom:1px solid #e5e9e6}.spatial-form label>span{display:block;margin-bottom:6px;color:#53665b;font-size:10px;font-weight:750}.spatial-form input,.spatial-form textarea{width:100%;border:1px solid #d7dfda;border-radius:5px;background:#fff;padding:0 8px;color:#2f4438;font:500 10px/1.3 inherit;outline:none}.spatial-form input{height:34px}.spatial-form textarea{padding-top:8px;resize:vertical}.coordinate-inputs{display:grid;grid-template-columns:1fr 1fr;gap:6px}.spatial-meta{display:grid;grid-template-columns:1fr 1fr;border:1px solid #e1e6e3;border-radius:6px}.spatial-meta span{padding:9px;border-right:1px solid #e5e9e6;border-bottom:1px solid #e5e9e6}.spatial-meta span:nth-child(2n){border-right:0}.spatial-meta span:nth-last-child(-n+2){border-bottom:0}.spatial-meta small,.spatial-meta strong{display:block}.spatial-meta small{color:#859088;font-size:9px}.spatial-meta strong{margin-top:4px;font-size:10px}
.spatial-history{min-height:0;overflow-y:auto;padding:13px 14px}.spatial-history h3{display:flex;align-items:center;gap:6px;margin:0 0 12px;font-size:12px}.spatial-history ol{margin:0;padding:0;list-style:none}.spatial-history li{position:relative;display:grid;grid-template-columns:12px 1fr;gap:7px;padding-bottom:13px}.spatial-history li:not(:last-child)::before{content:"";position:absolute;left:4px;top:9px;bottom:0;width:1px;background:#dbe2de}.spatial-history li i{position:relative;z-index:1;width:9px;height:9px;margin-top:2px;border:2px solid #fff;border-radius:50%;background:#168653;box-shadow:0 0 0 1px #9ac8af}.spatial-history strong,.spatial-history span,.spatial-history small{display:block}.spatial-history strong{font-size:10px}.spatial-history span{margin-top:3px;color:#87928c;font-size:8px}.spatial-history small{margin-top:4px;color:#65766d;font-size:9px;line-height:1.45}.spatial-no-history{padding:24px 0;text-align:center;color:#8a958f;font-size:10px}
.spatial-inspector>footer{display:grid;grid-template-columns:1fr 1.35fr;gap:8px;padding:12px 14px;border-top:1px solid #dfe5e1}.spatial-inspector>footer button{height:37px;display:flex;align-items:center;justify-content:center;gap:5px;border-radius:6px;font:750 10px/1 inherit;cursor:pointer}.spatial-inspector>footer .secondary{border:1px solid #168653;background:#fff;color:#14734a}.spatial-inspector>footer .primary{border:0;background:#0f754a;color:#fff}.spatial-inspector>footer button:disabled{opacity:.55}.spatial-inspector.empty{display:grid;place-items:center;color:#819087;font-size:11px}.spatial-loading{position:absolute;inset:0;z-index:30;display:grid;place-items:center;background:rgba(255,255,255,.68);color:#166f49;font-size:12px}
:global(.calibration-map-marker){width:24px;height:28px;border:0;background:transparent;padding:0;cursor:pointer}:global(.calibration-draft-marker){width:30px;height:32px}
:global(.calibration-map-marker span){display:block;width:18px;height:18px;border:3px solid #fff;border-radius:50% 50% 50% 4px;background:#d99017;box-shadow:0 1px 4px rgba(26,62,42,.28);transform:rotate(-45deg)}
:global(.calibration-map-marker.verified span){background:#168653}
:global(.calibration-map-marker.danger span){background:#d4423b}
:global(.calibration-map-marker.active span){width:24px;height:24px;box-shadow:0 0 0 5px rgba(22,134,83,.2),0 2px 6px rgba(20,55,36,.3)}
:global(.calibration-draft-marker span){display:block;width:25px;height:25px;border:4px solid #fff;border-radius:50% 50% 50% 4px;background:#2772c5;box-shadow:0 0 0 6px rgba(39,114,197,.2);transform:rotate(-45deg)}
@media(max-width:1180px){.spatial-workspace{height:auto;min-height:0;grid-template-columns:220px minmax(430px,1fr)}.spatial-map-panel{min-height:590px}.spatial-inspector{grid-column:1/-1;min-height:500px;border-top:1px solid #dfe5e1;border-left:0}}
@media(max-width:760px){.spatial-summary{grid-template-columns:1fr 1fr}.spatial-summary article:nth-child(2){border-right:0}.spatial-summary article:nth-child(-n+2){border-bottom:1px solid #e4e9e6}.spatial-workspace{display:flex;flex-direction:column}.spatial-node-rail{height:310px;border-right:0;border-bottom:1px solid #dfe5e1}.spatial-map-panel{min-height:500px}.spatial-inspector{min-height:560px}.spatial-crs{top:auto;bottom:12px}.spatial-map-hint{bottom:50px}}
</style>
