<script setup lang="ts">
import { CheckCircle2, Clock3, KeyRound, LockKeyhole, ShieldCheck } from '@lucide/vue'

const policies = [
  { icon: Clock3, title: '会话有效期', value: '60 分钟', description: '访问令牌到期后必须重新验证身份。' },
  { icon: LockKeyhole, title: '登录失败锁定', value: '5 次 / 15 分钟', description: '连续失败达到阈值后自动锁定账号。' },
  { icon: KeyRound, title: '密码复杂度', value: '至少 12 位', description: '必须包含大小写字母、数字和特殊字符。' },
  { icon: ShieldCheck, title: '敏感信息保护', value: '强制启用', description: '密码只存储哈希，API Key 加密入库，审计详情自动脱敏。' },
]
</script>

<template>
  <section class="security-page">
    <div class="page-title"><h2>安全策略</h2><p>查看当前平台身份验证与敏感信息保护基线</p></div>
    <div class="policy-list">
      <article v-for="policy in policies" :key="policy.title">
        <span><component :is="policy.icon" :size="21" /></span>
        <div><h3>{{ policy.title }}</h3><p>{{ policy.description }}</p></div>
        <strong>{{ policy.value }}</strong>
        <CheckCircle2 :size="18" class="check" />
      </article>
    </div>
    <div class="managed-note">
      <ShieldCheck :size="21" />
      <div><h3>生产环境基线</h3><p>安全策略由服务端统一执行，浏览器无法绕过。策略参数通过部署环境管理，修改后需要重新签发访问令牌。</p></div>
    </div>
  </section>
</template>

<style scoped>
.security-page{display:flex;flex-direction:column;gap:20px}.page-title h2{margin:0;font-size:25px;color:#22372d}.page-title p{margin:8px 0 0;color:#748178;font-size:13px}.policy-list{overflow:hidden;border:1px solid #dde4df;border-radius:10px;background:#fff}.policy-list article{display:grid;grid-template-columns:auto 1fr auto auto;align-items:center;gap:15px;min-height:84px;padding:0 20px;border-bottom:1px solid #e6ebe7}.policy-list article:last-child{border:0}.policy-list article>span{width:42px;height:42px;display:grid;place-items:center;border-radius:10px;background:#eaf5ef;color:#15734b}.policy-list h3{margin:0;color:#2a4034;font-size:14px}.policy-list p{margin:6px 0 0;color:#7a8780;font-size:12px}.policy-list strong{color:#1d5d3c;font-size:13px}.check{color:#19925b}.managed-note{display:flex;gap:13px;padding:17px;border:1px solid #cce4d5;border-radius:9px;background:#eef8f2;color:#176c47}.managed-note h3{margin:0;font-size:14px}.managed-note p{margin:6px 0 0;color:#557468;font-size:12px;line-height:1.7}
</style>
