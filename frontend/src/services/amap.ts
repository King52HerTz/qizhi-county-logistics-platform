import type { MapRuntimeConfig } from '../types/logistics'

declare global {
  interface Window {
    AMap?: any
    _AMapSecurityConfig?: { serviceHost?: string }
  }
}

let loading: Promise<void> | undefined

export function loadAmap(runtime: MapRuntimeConfig) {
  if (window.AMap) return Promise.resolve()
  if (loading) return loading
  window._AMapSecurityConfig = {
    serviceHost: runtime.service_host
      ? `${window.location.origin}${runtime.service_host}`
      : undefined,
  }
  loading = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById('qizhi-amap-js') as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('高德地图脚本加载失败')), {
        once: true,
      })
      return
    }
    const script = document.createElement('script')
    script.id = 'qizhi-amap-js'
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(runtime.web_key ?? '')}`
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('高德地图脚本加载失败'))
    document.head.appendChild(script)
  })
  return loading
}

export function loadAmapPlugin(name: string) {
  return new Promise<void>((resolve) => window.AMap.plugin(name, resolve))
}
