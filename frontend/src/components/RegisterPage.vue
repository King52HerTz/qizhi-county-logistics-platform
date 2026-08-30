<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Route,
  ShieldCheck,
  Sparkles,
  UserPlus,
} from '@lucide/vue'
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { register } from '../services/api'
import type { TokenResponse } from '../types/logistics'

const emit = defineEmits<{ authenticated: [session: TokenResponse] }>()
const displayName = ref('')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const agreementAccepted = ref(false)
const remember = ref(false)
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')

const passwordRules = computed(() => [
  { label: '至少 12 个字符', valid: password.value.length >= 12 },
  { label: '包含大小写字母', valid: /[a-z]/.test(password.value) && /[A-Z]/.test(password.value) },
  { label: '包含数字和特殊字符', valid: /\d/.test(password.value) && /[^A-Za-z0-9]/.test(password.value) },
])
const usernameValid = computed(() => /^[a-zA-Z][a-zA-Z0-9_.-]{2,63}$/.test(username.value))
const passwordValid = computed(() => passwordRules.value.every(rule => rule.valid))
const canSubmit = computed(() =>
  displayName.value.trim().length >= 2
  && usernameValid.value
  && passwordValid.value
  && password.value === confirmPassword.value
  && agreementAccepted.value,
)

async function submit() {
  if (!canSubmit.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const session = await register({
      username: username.value.trim(),
      display_name: displayName.value.trim(),
      password: password.value,
      agreement_accepted: true,
    }, remember.value)
    emit('authenticated', session)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '账号创建失败，请稍后重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="register-page">
    <section class="register-story" aria-label="账号安全说明">
      <div class="story-inner">
        <div class="register-brand"><span><Route :size="25" /></span><div><strong>祁智运</strong><small>AI LOGISTICS OS</small></div></div>
        <div class="story-copy">
          <p class="story-kicker"><Sparkles :size="16" /> 统一身份与权限管理</p>
          <h1>创建专属账号，<br />进入协同运营空间</h1>
          <p>新账号默认采用最小权限策略，仅可提交配送申请并跟踪本人订单；调度、审批与敏感配置仅对授权人员开放。</p>
        </div>
        <div class="security-list">
          <div><ShieldCheck :size="19" /><span><b>最小权限</b><small>公开注册无法获取管理员权限</small></span></div>
          <div><Check :size="19" /><span><b>安全存储</b><small>密码经加盐哈希后保存</small></span></div>
          <div><UserPlus :size="19" /><span><b>全程留痕</b><small>注册、登录和关键操作均可审计</small></span></div>
        </div>
      </div>
    </section>

    <section class="register-panel">
      <div class="register-box">
        <RouterLink class="back-login" to="/login"><ArrowLeft :size="16" /> 返回登录</RouterLink>
        <div class="register-heading">
          <div class="register-icon"><UserPlus :size="23" /></div>
          <p>创建账号</p>
          <h2>注册用户账号</h2>
          <span>注册成功后可提交配送申请并跟踪处理进度</span>
        </div>
        <form @submit.prevent="submit">
          <div class="field-row">
            <label><span>姓名或称呼</span><input v-model="displayName" autocomplete="name" maxlength="100" placeholder="例如：王师傅" required /></label>
            <label>
              <span>登录账号</span>
              <input v-model.trim="username" autocomplete="username" maxlength="64" placeholder="字母开头" required />
              <small v-if="username && !usernameValid" class="field-error">仅支持字母、数字、点、短横线和下划线</small>
            </label>
          </div>
          <label>
            <span>登录密码</span>
            <div class="password-input">
              <input v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" maxlength="128" placeholder="设置高强度密码" required />
              <button type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
                <EyeOff v-if="showPassword" :size="18" /><Eye v-else :size="18" />
              </button>
            </div>
            <div class="password-rules">
              <span v-for="rule in passwordRules" :key="rule.label" :class="{ valid: rule.valid }"><Check :size="13" />{{ rule.label }}</span>
            </div>
          </label>
          <label>
            <span>确认密码</span>
            <input v-model="confirmPassword" type="password" autocomplete="new-password" maxlength="128" placeholder="再次输入密码" required />
            <small v-if="confirmPassword && password !== confirmPassword" class="field-error">两次输入的密码不一致</small>
          </label>
          <div class="register-options">
            <label><input v-model="agreementAccepted" type="checkbox" /><span>我已阅读并同意平台账号与数据使用规范</span></label>
            <label><input v-model="remember" type="checkbox" /><span>在此设备保持登录</span></label>
          </div>
          <div v-if="error" class="register-error" role="alert"><AlertCircle :size="17" /><span>{{ error }}</span></div>
          <button class="register-button" :disabled="!canSubmit || busy">
            <span>{{ busy ? '正在创建账号…' : '创建账号并进入平台' }}</span><ArrowRight :size="18" />
          </button>
        </form>
        <footer>© 2026 祁智运 · 县域物流智能决策平台</footer>
      </div>
    </section>
  </main>
</template>

<style scoped>
.register-page,.register-page *{box-sizing:border-box}.register-page{min-height:100vh;display:grid;grid-template-columns:minmax(430px,.88fr) minmax(620px,1.12fr);background:#f7f8f6;color:#183228}
.register-story{position:relative;overflow:hidden;background:#0d5138;color:#fff}.register-story::before,.register-story::after{content:"";position:absolute;border:1px solid rgba(255,255,255,.09);border-radius:50%}.register-story::before{width:560px;height:560px;right:-260px;top:-120px}.register-story::after{width:380px;height:380px;left:-190px;bottom:-140px}
.story-inner{position:relative;z-index:1;min-height:100vh;max-width:650px;margin:auto;padding:44px 9%;display:flex;flex-direction:column}.register-brand{display:flex;align-items:center;gap:12px}.register-brand>span{width:44px;height:44px;display:grid;place-items:center;border-radius:12px;background:#f5b83b;color:#124e38}.register-brand strong{display:block;font-size:20px}.register-brand small{display:block;margin-top:3px;font-size:10px;letter-spacing:1.8px;color:#b8d2c6}
.story-copy{margin:auto 0 45px}.story-kicker{display:flex;align-items:center;gap:8px;margin:0 0 18px;color:#c9ded4;font-size:14px;font-weight:700}.story-copy h1{margin:0;font-size:39px;line-height:1.28;letter-spacing:-1px}.story-copy>p:last-child{max-width:520px;margin:20px 0 0;color:#c2d7cd;font-size:15px;line-height:1.8}
.security-list{display:grid;gap:10px;margin-bottom:18px}.security-list>div{display:flex;align-items:center;gap:12px;padding:13px 15px;border:1px solid rgba(255,255,255,.12);border-radius:12px;background:rgba(255,255,255,.055);color:#f5c75d}.security-list span,.security-list b,.security-list small{display:block}.security-list b{color:#fff;font-size:13px}.security-list small{margin-top:3px;color:#a9c8b9;font-size:11px}
.register-panel{display:grid;place-items:center;padding:30px 52px}.register-box{width:min(620px,100%)}.back-login{display:inline-flex;align-items:center;gap:6px;margin-bottom:20px;color:#557068;font-size:13px;font-weight:700;text-decoration:none}.back-login:hover{color:#126b47}
.register-heading{margin-bottom:22px}.register-icon{width:45px;height:45px;display:grid;place-items:center;border-radius:13px;background:#e8f3ed;color:#126a46}.register-heading p{margin:15px 0 4px;color:#17744e;font-size:13px;font-weight:800}.register-heading h2{margin:0;font-size:27px;letter-spacing:-.5px}.register-heading>span{display:block;margin-top:7px;color:#728079;font-size:13px}
form{display:flex;flex-direction:column;gap:15px}.field-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:flex;flex-direction:column;gap:7px}label>span{font-size:13px;font-weight:700;color:#30473b}input{width:100%;height:45px;border:1px solid #d7dfda;border-radius:10px;padding:0 13px;background:#fff;color:#1c3328;font-size:14px;outline:none}input:focus{border-color:#178050;box-shadow:0 0 0 3px rgba(23,128,80,.12)}
.password-input{position:relative}.password-input input{padding-right:48px}.password-input button{position:absolute;right:3px;top:3px;width:39px;height:39px;border:0;background:transparent;color:#6f7e76;cursor:pointer}.password-rules{display:flex;flex-wrap:wrap;gap:6px 13px}.password-rules span{display:flex;align-items:center;gap:4px;color:#8b9791;font-size:11px}.password-rules span.valid{color:#168052}.field-error{color:#b0463e;font-size:11px}
.register-options{display:flex;justify-content:space-between;gap:15px;padding:2px 0}.register-options label{display:flex;flex-direction:row;align-items:center;gap:7px}.register-options input{width:16px;height:16px;accent-color:#16764c}.register-options span{font-size:12px;font-weight:500;color:#56685f}
.register-error{display:flex;align-items:flex-start;gap:9px;padding:10px 12px;border:1px solid #efd0cd;border-radius:9px;background:#fff2f1;color:#a83d37;font-size:12px;line-height:1.5}.register-button{height:47px;display:flex;align-items:center;justify-content:center;gap:10px;border:0;border-radius:10px;background:#126b47;color:#fff;font-size:14px;font-weight:800;cursor:pointer;box-shadow:0 5px 14px rgba(18,107,71,.18)}.register-button:hover:not(:disabled){background:#0d5c3c}.register-button:disabled{opacity:.5;cursor:not-allowed}.register-box footer{margin-top:20px;color:#9aa49f;font-size:11px;text-align:center}
@media(max-width:900px){.register-page{display:block}.register-story{display:none}.register-panel{min-height:100vh;padding:24px 20px}.register-box{max-width:520px}.field-row{grid-template-columns:1fr}.register-options{flex-direction:column;gap:10px}.register-heading h2{font-size:24px}}
</style>
