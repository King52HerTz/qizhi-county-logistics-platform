<script setup lang="ts">
import { ArrowLeft, ArrowRight, CircleHelp, MousePointer2, X } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

interface OperationGuideStep {
  eyebrow: string
  title: string
  description: string
  tip: string
  target: string
  actionLabel: string
}

const props = defineProps<{
  open: boolean
  step: OperationGuideStep
  current: number
  total: number
}>()

const emit = defineEmits<{
  next: []
  previous: []
  close: []
}>()

type TargetBox = {
  top: number
  right: number
  bottom: number
  left: number
  width: number
  height: number
}

const padding = 8
const targetBox = ref<TargetBox>()
const dialog = ref<HTMLElement>()
let previousOverflow = ''
let locateTimer: number | undefined

const viewport = () => ({
  width: window.innerWidth,
  height: window.innerHeight,
})

function locateTarget() {
  if (!props.open) return false
  const element = document.querySelector<HTMLElement>(props.step.target)
  if (!element) {
    targetBox.value = undefined
    return false
  }
  element.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  const rect = element.getBoundingClientRect()
  targetBox.value = {
    top: rect.top,
    right: rect.right,
    bottom: rect.bottom,
    left: rect.left,
    width: rect.width,
    height: rect.height,
  }
  return true
}

const maskStyles = computed(() => {
  if (!targetBox.value) return []
  const box = targetBox.value
  const { width, height } = viewport()
  const top = Math.max(0, box.top - padding)
  const left = Math.max(0, box.left - padding)
  const right = Math.min(width, box.right + padding)
  const bottom = Math.min(height, box.bottom + padding)
  return [
    { top: '0', left: '0', width: '100%', height: `${top}px` },
    { top: `${top}px`, left: '0', width: `${left}px`, height: `${bottom - top}px` },
    { top: `${top}px`, left: `${right}px`, width: `${Math.max(0, width - right)}px`, height: `${bottom - top}px` },
    { top: `${bottom}px`, left: '0', width: '100%', height: `${Math.max(0, height - bottom)}px` },
  ]
})

const highlightStyle = computed(() => {
  if (!targetBox.value) return { display: 'none' }
  const box = targetBox.value
  return {
    top: `${box.top - padding}px`,
    left: `${box.left - padding}px`,
    width: `${box.width + padding * 2}px`,
    height: `${box.height + padding * 2}px`,
  }
})

const cardStyle = computed(() => {
  const { width, height } = viewport()
  const cardWidth = Math.min(380, width - 24)
  if (!targetBox.value || width <= 720) {
    return {
      left: `${Math.max(12, (width - cardWidth) / 2)}px`,
      bottom: '16px',
      width: `${cardWidth}px`,
    }
  }
  const box = targetBox.value
  let left = box.right + 22
  if (left + cardWidth > width - 16) left = box.left - cardWidth - 22
  if (left < 16) left = Math.max(16, (width - cardWidth) / 2)
  const estimatedHeight = 310
  const top = Math.max(16, Math.min(box.top, height - estimatedHeight - 16))
  return { left: `${left}px`, top: `${top}px`, width: `${cardWidth}px` }
})

function handleKeydown(event: KeyboardEvent) {
  if (!props.open) return
  if (event.key === 'Escape') emit('close')
  if (event.key === 'ArrowRight') emit('next')
  if (event.key === 'ArrowLeft' && props.current > 0) emit('previous')
}

async function refresh() {
  await nextTick()
  if (locateTimer !== undefined) window.clearTimeout(locateTimer)
  let attempts = 0
  const tryLocate = () => {
    attempts += 1
    if (!locateTarget() && attempts < 30) {
      locateTimer = window.setTimeout(tryLocate, 100)
      return
    }
    dialog.value?.focus()
  }
  locateTimer = window.setTimeout(tryLocate, 80)
}

watch(
  () => [props.open, props.current, props.step.target],
  async () => {
    if (props.open) {
      previousOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      await refresh()
    } else {
      if (locateTimer !== undefined) window.clearTimeout(locateTimer)
      document.body.style.overflow = previousOverflow
      targetBox.value = undefined
    }
  },
  { immediate: true },
)

onMounted(() => {
  window.addEventListener('resize', locateTarget)
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.body.style.overflow = previousOverflow
  if (locateTimer !== undefined) window.clearTimeout(locateTimer)
  window.removeEventListener('resize', locateTarget)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="operation-guide" aria-live="polite">
      <div
        v-for="(style, index) in maskStyles"
        :key="index"
        class="guide-mask"
        :style="style"
      />
      <div v-if="!targetBox" class="guide-mask guide-mask-full" />
      <div class="guide-highlight" :style="highlightStyle">
        <span class="guide-pulse"><MousePointer2 :size="15" /></span>
      </div>

      <section
        ref="dialog"
        class="guide-card"
        :style="cardStyle"
        role="dialog"
        aria-modal="true"
        :aria-label="`操作引导：${step.title}`"
        tabindex="-1"
      >
        <header>
          <span class="guide-symbol"><CircleHelp :size="20" /></span>
          <div>
            <small>{{ step.eyebrow }}</small>
            <b>{{ current + 1 }} / {{ total }}</b>
          </div>
          <button type="button" aria-label="退出操作引导" @click="emit('close')"><X :size="18" /></button>
        </header>
        <div class="guide-progress"><i :style="{ width: `${((current + 1) / total) * 100}%` }" /></div>
        <h2>{{ step.title }}</h2>
        <p>{{ step.description }}</p>
        <div class="guide-tip"><MousePointer2 :size="16" /><span>{{ step.tip }}</span></div>
        <footer>
          <button v-if="current > 0" class="guide-back" type="button" @click="emit('previous')">
            <ArrowLeft :size="15" />上一步
          </button>
          <span v-else />
          <button class="guide-next" type="button" @click="emit('next')">
            {{ step.actionLabel }}<ArrowRight :size="16" />
          </button>
        </footer>
        <small class="guide-safety">引导只切换页面，不会自动提交、重算或下发任务。</small>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.operation-guide{position:fixed;inset:0;z-index:5000;font-family:inherit}
.guide-mask{position:fixed;background:rgba(7,28,20,.72);backdrop-filter:blur(1px);pointer-events:auto}
.guide-mask-full{inset:0;width:100%;height:100%}
.guide-highlight{position:fixed;border:2px solid #f5bd47;border-radius:12px;box-shadow:0 0 0 4px rgba(245,189,71,.22),0 10px 35px rgba(0,0,0,.24);pointer-events:none;transition:all .25s ease}
.guide-pulse{position:absolute;right:-11px;bottom:-11px;width:28px;height:28px;display:grid;place-items:center;border-radius:50%;background:#f5b83b;color:#174b37;box-shadow:0 0 0 0 rgba(245,184,59,.6);animation:guide-pulse 1.8s infinite}
.guide-card{position:fixed;z-index:2;padding:20px;border:1px solid rgba(255,255,255,.72);border-radius:16px;background:#fff;color:#17372b;box-shadow:0 24px 70px rgba(4,28,19,.3);outline:none}
.guide-card header{display:flex;align-items:center;gap:11px}.guide-symbol{width:38px;height:38px;display:grid;place-items:center;border-radius:11px;background:#e8f4ed;color:#137149}
.guide-card header>div{display:flex;flex:1;flex-direction:column;gap:2px}.guide-card header small{font-size:11px;font-weight:800;letter-spacing:.6px;color:#168053}.guide-card header b{font-size:12px;color:#7d8b84}
.guide-card header>button{width:32px;height:32px;display:grid;place-items:center;border:0;border-radius:8px;background:#f3f6f4;color:#6a7971;cursor:pointer}.guide-card header>button:hover{background:#e8eeea;color:#1d4937}
.guide-progress{height:3px;margin:16px 0 18px;overflow:hidden;border-radius:99px;background:#e7ede9}.guide-progress i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#168052,#f3b33b);transition:width .25s ease}
.guide-card h2{margin:0;font-size:21px;line-height:1.3;letter-spacing:-.3px}.guide-card>p{margin:10px 0 14px;color:#5e7066;font-size:14px;line-height:1.7}
.guide-tip{display:flex;align-items:flex-start;gap:9px;padding:11px 12px;border-radius:10px;background:#f3f8f5;color:#295b45;font-size:13px;line-height:1.55}.guide-tip svg{flex:0 0 auto;margin-top:2px;color:#168052}
.guide-card footer{display:flex;justify-content:space-between;gap:12px;margin-top:18px}.guide-card footer button{height:38px;display:flex;align-items:center;justify-content:center;gap:7px;padding:0 14px;border-radius:9px;font-size:13px;font-weight:800;cursor:pointer}
.guide-back{border:1px solid #d7e1db;background:#fff;color:#52675b}.guide-next{border:0;background:#146f49;color:#fff;box-shadow:0 5px 14px rgba(20,111,73,.18)}.guide-next:hover{background:#0f5f3e}
.guide-safety{display:block;margin-top:12px;color:#98a39d;font-size:10px;text-align:center}
@keyframes guide-pulse{70%{box-shadow:0 0 0 12px rgba(245,184,59,0)}100%{box-shadow:0 0 0 0 rgba(245,184,59,0)}}
@media(max-width:720px){.guide-card{padding:17px}.guide-card h2{font-size:18px}.guide-card>p{font-size:13px}.guide-highlight{border-radius:9px}.guide-safety{line-height:1.5}}
@media(prefers-reduced-motion:reduce){.guide-highlight{transition:none}.guide-pulse{animation:none}}
</style>
