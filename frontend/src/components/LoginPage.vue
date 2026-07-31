<script setup lang="ts">
import { AlertCircle, ArrowRight, CheckCircle2, Eye, EyeOff, LockKeyhole, Route, ShieldCheck, Sparkles, Truck } from '@lucide/vue'
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { login } from '../services/api'
import type { TokenResponse } from '../types/logistics'

const emit = defineEmits<{ authenticated: [session: TokenResponse] }>()
const username = ref('admin')
const password = ref('')
const remember = ref(false)
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')
const canSubmit = computed(() => username.value.trim().length >= 3 && password.value.length >= 8)

async function submit() {
  if (!canSubmit.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    emit('authenticated', await login(username.value.trim(), password.value, remember.value))
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '登录失败，请稍后重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="enterprise-login">
    <section class="login-story" aria-label="平台能力介绍">
      <div class="story-inner">
        <div class="login-brand"><span><Route :size="25" /></span><div><strong>祁智运</strong><small>AI LOGISTICS OS</small></div></div>
        <div class="story-copy">
          <p class="story-kicker"><Sparkles :size="16" /> 衡阳市县域物流智能决策平台</p>
          <h1>让每一次调度，<br />都可计算、可执行、可追溯</h1>
          <p>面向县域城乡双向配送，以确定性优化引擎统筹订单、运力、时间窗与冷链约束。</p>
        </div>
        <div class="capabilities">
          <div><span><Truck :size="19" /></span><p><b>智能调度</b><small>多约束车辆路径优化</small></p></div>
          <div><span><Route :size="19" /></span><p><b>路径规划</b><small>路网成本与动态重调度</small></p></div>
          <div><span><ShieldCheck :size="19" /></span><p><b>全程留痕</b><small>审批、下发与执行闭环</small></p></div>
        </div>
        <div class="service-state"><span><i /> 服务运行正常</span><small>生产环境 · 数据加密传输</small></div>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-box">
        <div class="mobile-brand"><Route :size="22" /><strong>祁智运</strong></div>
        <div class="login-heading">
          <div class="login-icon"><LockKeyhole :size="23" /></div>
          <p>欢迎回来</p>
          <h2>登录运营管理平台</h2>
          <span>使用企业账号登录，或创建一个新的运营账号</span>
        </div>
        <form @submit.prevent="submit">
          <label><span>账号</span><input v-model.trim="username" autocomplete="username" placeholder="请输入账号" required /></label>
          <label>
            <span>密码</span>
            <div class="password-input">
              <input v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" required />
              <button type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
                <EyeOff v-if="showPassword" :size="18" /><Eye v-else :size="18" />
              </button>
            </div>
          </label>
          <div class="login-options">
            <label class="remember"><input v-model="remember" type="checkbox" /><span>在此设备保持登录</span></label>
            <span class="help-text">忘记密码请联系系统管理员</span>
          </div>
          <div v-if="error" class="login-error" role="alert"><AlertCircle :size="17" /><span>{{ error }}</span></div>
          <button class="login-button" :disabled="!canSubmit || busy">
            <span>{{ busy ? '正在验证身份…' : '安全登录' }}</span><ArrowRight :size="18" />
          </button>
        </form>
        <div class="register-entry">
          <span>还没有账号？</span>
          <RouterLink to="/register">创建运营账号</RouterLink>
        </div>
        <div class="security-note"><CheckCircle2 :size="16" /><span>连续 5 次登录失败将锁定账号 15 分钟</span></div>
        <footer>© 2026 祁智运 · 县域物流智能决策平台</footer>
      </div>
    </section>
  </main>
</template>

<style scoped>
.enterprise-login,.enterprise-login *{box-sizing:border-box}
.enterprise-login{min-height:100vh;display:grid;grid-template-columns:minmax(480px,1.05fr) minmax(480px,.95fr);background:#f7f8f6;color:#183228}
.login-story{position:relative;overflow:hidden;background:#0d5138;color:#fff}
.login-story::before,.login-story::after{content:"";position:absolute;border:1px solid rgba(255,255,255,.09);border-radius:50%}
.login-story::before{width:620px;height:620px;right:-260px;top:-150px}.login-story::after{width:420px;height:420px;left:-210px;bottom:-180px}
.story-inner{position:relative;z-index:1;min-height:100vh;max-width:720px;margin:auto;padding:48px 9%;display:flex;flex-direction:column}
.login-brand,.mobile-brand{display:flex;align-items:center;gap:12px}.login-brand>span{width:44px;height:44px;display:grid;place-items:center;border-radius:12px;background:#f5b83b;color:#124e38}
.login-brand strong{display:block;font-size:20px}.login-brand small{display:block;margin-top:3px;font-size:10px;letter-spacing:1.8px;color:#b8d2c6}
.story-copy{margin:auto 0 56px}.story-kicker{display:flex;align-items:center;gap:8px;margin:0 0 18px;color:#c9ded4;font-size:14px;font-weight:700}
.story-copy h1{margin:0;font-size:42px;line-height:1.25;letter-spacing:-1px}.story-copy>p:last-child{max-width:570px;margin:20px 0 0;color:#c2d7cd;font-size:16px;line-height:1.8}
.capabilities{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:34px}.capabilities>div{display:flex;gap:11px;padding:15px;border:1px solid rgba(255,255,255,.12);border-radius:12px;background:rgba(255,255,255,.055)}
.capabilities>div>span{width:34px;height:34px;display:grid;place-items:center;border-radius:9px;background:rgba(245,184,59,.16);color:#f5c75d}.capabilities p{margin:0}.capabilities b,.capabilities small{display:block}.capabilities b{font-size:13px}.capabilities small{margin-top:5px;color:#a9c8b9;font-size:11px}
.service-state{display:flex;justify-content:space-between;padding-top:19px;border-top:1px solid rgba(255,255,255,.12);font-size:12px;color:#b6d0c4}.service-state span{display:flex;align-items:center;gap:8px}.service-state i{width:8px;height:8px;border-radius:50%;background:#5dd68a;box-shadow:0 0 0 4px rgba(93,214,138,.12)}
.login-panel{display:grid;place-items:center;padding:48px}.login-box{width:min(440px,100%)}.mobile-brand{display:none}.login-heading{margin-bottom:30px}.login-icon{width:48px;height:48px;display:grid;place-items:center;border-radius:13px;background:#e8f3ed;color:#126a46}
.login-heading p{margin:22px 0 6px;color:#17744e;font-size:13px;font-weight:800}.login-heading h2{margin:0;font-size:28px;letter-spacing:-.5px}.login-heading>span{display:block;margin-top:10px;color:#728079;font-size:14px}
form{display:flex;flex-direction:column;gap:19px}form>label{display:flex;flex-direction:column;gap:8px}form>label>span{font-size:14px;font-weight:700;color:#30473b}
input{width:100%;height:48px;border:1px solid #d7dfda;border-radius:10px;padding:0 14px;background:#fff;color:#1c3328;font-size:15px;outline:none}input:focus{border-color:#178050;box-shadow:0 0 0 3px rgba(23,128,80,.12)}
.password-input{position:relative}.password-input input{padding-right:48px}.password-input button{position:absolute;right:4px;top:4px;width:40px;height:40px;border:0;background:transparent;color:#6f7e76;cursor:pointer}
.login-options{display:flex;align-items:center;justify-content:space-between;gap:18px}.remember{display:flex;align-items:center;gap:8px;font-size:13px;color:#4c5f55}.remember input{width:17px;height:17px;accent-color:#16764c}.help-text{font-size:12px;color:#718077}
.login-error{display:flex;align-items:flex-start;gap:9px;padding:11px 13px;border:1px solid #efd0cd;border-radius:9px;background:#fff2f1;color:#a83d37;font-size:13px;line-height:1.5}
.login-button{height:48px;display:flex;align-items:center;justify-content:center;gap:10px;border:0;border-radius:10px;background:#126b47;color:#fff;font-size:15px;font-weight:800;cursor:pointer;box-shadow:0 5px 14px rgba(18,107,71,.18)}.login-button:hover:not(:disabled){background:#0d5c3c}.login-button:disabled{opacity:.55;cursor:not-allowed}
.register-entry{display:flex;align-items:center;justify-content:center;gap:7px;margin-top:18px;color:#718077;font-size:13px}.register-entry a{color:#126b47;font-weight:800;text-decoration:none}.register-entry a:hover{text-decoration:underline}
.security-note{display:flex;align-items:center;gap:8px;margin-top:20px;padding:12px;border-radius:9px;background:#eef5f1;color:#547064;font-size:12px}.security-note svg{color:#178050}.login-box footer{margin-top:30px;color:#9aa49f;font-size:11px;text-align:center}
@media(max-width:900px){.enterprise-login{display:block}.login-story{display:none}.login-panel{min-height:100vh;padding:32px 22px}.mobile-brand{display:flex;margin-bottom:50px;color:#135f41}.login-heading h2{font-size:25px}.login-options{align-items:flex-start;flex-direction:column;gap:10px}}
</style>
