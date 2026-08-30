<script setup lang="ts">
import { LogOut, Route, ShieldCheck, UserRound } from '@lucide/vue'
import { useRouter } from 'vue-router'
import OrderRequestCenter from './OrderRequestCenter.vue'
import { getSessionUser, logout } from '../services/api'

const router = useRouter()
const sessionUser = getSessionUser()

async function signOut() {
  await logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="customer-shell">
    <header class="customer-topbar">
      <div class="customer-brand"><span><Route :size="22" /></span><div><strong>祁智运</strong><small>AI LOGISTICS</small></div></div>
      <div class="customer-actions"><span class="service-state"><i />服务在线</span><span class="customer-account"><UserRound :size="15" />{{ sessionUser || '注册用户' }}</span><button type="button" @click="signOut"><LogOut :size="15" />退出</button></div>
    </header>
    <main class="customer-main">
      <div class="customer-heading"><div><p><ShieldCheck :size="15" /> 用户服务工作台</p><h1>订单申请与配送跟踪</h1><span>提交配送需求，查看审核进度，并掌握正式运营订单的处理状态。</span></div><div class="customer-badge">账号权限：订单用户</div></div>
      <OrderRequestCenter mode="user" />
    </main>
  </div>
</template>

<style scoped>
.customer-shell{min-height:100vh;background:#f4f7f4;color:#18382a}.customer-topbar{height:70px;display:flex;align-items:center;justify-content:space-between;padding:0 6vw;background:#fff;border-bottom:1px solid #e2eae4;box-shadow:0 2px 15px rgba(25,65,44,.04)}.customer-brand{display:flex;align-items:center;gap:10px}.customer-brand>span{width:38px;height:38px;display:grid;place-items:center;border-radius:11px;background:#f3b73a;color:#124c35}.customer-brand strong{display:block;font-size:19px;letter-spacing:1px}.customer-brand small{display:block;margin-top:2px;color:#84918a;font-size:9px;letter-spacing:1.7px}.customer-actions{display:flex;align-items:center;gap:18px;color:#6b7d73;font-size:12px}.service-state{display:flex;align-items:center;gap:6px}.service-state i{width:7px;height:7px;border-radius:50%;background:#26a66b;box-shadow:0 0 0 4px #eaf7ef}.customer-account{display:flex;align-items:center;gap:6px;color:#385648;font-weight:700}.customer-actions button{display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border:1px solid #dce6df;border-radius:8px;background:#fff;color:#557064;cursor:pointer;font:inherit}.customer-actions button:hover{border-color:#168050;color:#168050}.customer-main{width:min(1180px,calc(100% - 48px));margin:0 auto;padding:40px 0 60px}.customer-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:25px}.customer-heading p{display:flex;align-items:center;gap:6px;margin:0 0 10px;color:#178050;font-size:13px;font-weight:800}.customer-heading h1{margin:0;color:#123c2b;font-size:31px;letter-spacing:-.8px}.customer-heading span{display:block;margin-top:9px;color:#718078;font-size:13px}.customer-badge{padding:9px 13px;border:1px solid #dcebe1;border-radius:99px;background:#eef8f1;color:#237552;font-size:12px;font-weight:700;white-space:nowrap}@media(max-width:680px){.customer-topbar{height:auto;min-height:64px;padding:12px 18px}.customer-actions{gap:8px}.service-state{display:none}.customer-account{max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.customer-main{width:calc(100% - 30px);padding-top:25px}.customer-heading{align-items:flex-start;flex-direction:column;margin-bottom:19px}.customer-heading h1{font-size:25px}.customer-badge{align-self:flex-start}}
</style>
