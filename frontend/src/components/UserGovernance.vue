<script setup lang="ts">
import { AlertCircle, Check, ChevronLeft, ChevronRight, Eye, EyeOff, KeyRound, LoaderCircle, LockKeyhole, Pencil, Plus, RefreshCw, Search, ShieldCheck, UserRound, UsersRound, X } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { createUser, getUsers, resetUserPassword, updateUser } from '../services/api'
import type { ManagedUser, UserCreateInput, UserRole } from '../types/logistics'

const users = ref<ManagedUser[]>([])
const total = ref(0)
const activeCount = ref(0)
const adminCount = ref(0)
const lockedCount = ref(0)
const loading = ref(true)
const saving = ref(false)
const page = ref(1)
const pageSize = 10
const filters = reactive({ search: '', role: '', status: '' })
const applied = reactive({ search: '', role: '', status: '' })
const drawerMode = ref<'create' | 'edit' | 'password'>('create')
const drawerOpen = ref(false)
const target = ref<ManagedUser>()
const showPassword = ref(false)
const showConfirm = ref(false)
const notice = ref<{ kind: 'success' | 'error'; text: string }>()
const form = reactive({
  display_name: '',
  username: '',
  role: 'dispatcher' as UserRole,
  password: '',
  confirm_password: '',
  is_active: true,
  unlock: false,
})

const roleNames: Record<UserRole, string> = {
  admin: '系统管理员',
  dispatcher: '调度员',
  driver: '驾驶员',
  viewer: '只读访客',
}
const permissionMap: Record<UserRole, Array<[string, string]>> = {
  admin: [['运营与调度', '完整访问'], ['场景与算法', '完整访问'], ['系统设置', '管理']],
  dispatcher: [['运营总览', '查看'], ['智能调度', '创建、查看'], ['执行中心', '提交与下发']],
  driver: [['驾驶任务', '查看与执行'], ['其他模块', '无访问权限']],
  viewer: [['运营总览', '只读'], ['历史方案', '只读'], ['管理功能', '无访问权限']],
}
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const passwordValid = computed(() =>
  form.password.length >= 12
  && /[a-z]/.test(form.password)
  && /[A-Z]/.test(form.password)
  && /\d/.test(form.password)
  && /[^A-Za-z0-9]/.test(form.password),
)
const canSave = computed(() => {
  if (!form.display_name.trim()) return false
  if (drawerMode.value === 'edit') return true
  return form.username.trim().length >= 3
    && passwordValid.value
    && form.password === form.confirm_password
})

function formatTime(value?: string) {
  if (!value) return '从未登录'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}
function params() {
  const query = new URLSearchParams({ limit: String(pageSize), offset: String((page.value - 1) * pageSize) })
  if (applied.search) query.set('search', applied.search)
  if (applied.role) query.set('role', applied.role)
  if (applied.status) query.set('status', applied.status)
  return query.toString()
}
async function load() {
  loading.value = true
  try {
    const result = await getUsers(params())
    users.value = result.items
    total.value = result.total
    activeCount.value = result.active_count
    adminCount.value = result.admin_count
    lockedCount.value = result.locked_count
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '用户列表加载失败' }
  } finally { loading.value = false }
}
function query() {
  Object.assign(applied, filters)
  page.value = 1
  load()
}
function resetFilters() {
  Object.assign(filters, { search: '', role: '', status: '' })
  query()
}
function resetForm() {
  Object.assign(form, {
    display_name: '', username: '', role: 'dispatcher', password: '',
    confirm_password: '', is_active: true, unlock: false,
  })
  showPassword.value = false
  showConfirm.value = false
}
function openCreate() {
  target.value = undefined
  drawerMode.value = 'create'
  resetForm()
  drawerOpen.value = true
}
function openEdit(user: ManagedUser) {
  target.value = user
  drawerMode.value = 'edit'
  resetForm()
  Object.assign(form, {
    display_name: user.display_name,
    username: user.username,
    role: user.role,
    is_active: user.is_active,
    unlock: false,
  })
  drawerOpen.value = true
}
function openPassword(user: ManagedUser) {
  target.value = user
  drawerMode.value = 'password'
  resetForm()
  form.display_name = user.display_name
  form.username = user.username
  drawerOpen.value = true
}
async function save() {
  if (!canSave.value || saving.value) return
  saving.value = true
  notice.value = undefined
  try {
    if (drawerMode.value === 'create') {
      await createUser({
        username: form.username.trim(),
        display_name: form.display_name.trim(),
        role: form.role,
        password: form.password,
        is_active: form.is_active,
      } satisfies UserCreateInput)
      notice.value = { kind: 'success', text: `用户“${form.display_name}”已创建` }
    } else if (drawerMode.value === 'edit' && target.value) {
      await updateUser(target.value.id, {
        display_name: form.display_name.trim(),
        role: form.role,
        is_active: form.is_active,
        unlock: form.unlock,
      })
      notice.value = { kind: 'success', text: '用户信息已更新' }
    } else if (drawerMode.value === 'password' && target.value) {
      await resetUserPassword(target.value.id, form.password)
      notice.value = { kind: 'success', text: `已重置 ${target.value.username} 的密码并解除登录锁定` }
    }
    drawerOpen.value = false
    await load()
  } catch (cause) {
    notice.value = { kind: 'error', text: cause instanceof Error ? cause.message : '操作失败' }
  } finally { saving.value = false }
}
async function changePage(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next))
  await load()
}

onMounted(load)
</script>

<template>
  <section class="governance-page">
    <div class="page-toolbar">
      <div><h2>用户与权限</h2><p>统一管理平台账号、角色与访问状态</p></div>
      <button class="primary" @click="openCreate"><Plus :size="18" />新建用户</button>
    </div>

    <div v-if="notice" class="notice" :class="notice.kind">
      <Check v-if="notice.kind === 'success'" :size="17" /><AlertCircle v-else :size="17" />
      <span>{{ notice.text }}</span><button @click="notice = undefined"><X :size="15" /></button>
    </div>

    <div class="summary-strip">
      <article><span><UsersRound :size="20" /></span><div><small>用户总数</small><strong>{{ total }}</strong></div></article>
      <article><span class="green"><Check :size="20" /></span><div><small>已启用</small><strong>{{ activeCount }}</strong></div></article>
      <article><span><ShieldCheck :size="20" /></span><div><small>管理员</small><strong>{{ adminCount }}</strong></div></article>
      <article><span class="red"><LockKeyhole :size="20" /></span><div><small>已锁定</small><strong>{{ lockedCount }}</strong></div></article>
    </div>

    <article class="user-table-card">
      <form class="filter-bar" @submit.prevent="query">
        <label class="search-field"><Search :size="17" /><input v-model.trim="filters.search" placeholder="搜索账号或姓名" /></label>
        <select v-model="filters.role"><option value="">全部角色</option><option v-for="(label,key) in roleNames" :key="key" :value="key">{{ label }}</option></select>
        <select v-model="filters.status"><option value="">全部状态</option><option value="active">已启用</option><option value="disabled">已停用</option><option value="locked">已锁定</option></select>
        <button class="query-button">查询</button>
        <button class="reset-button" type="button" @click="resetFilters"><RefreshCw :size="15" />重置</button>
      </form>
      <div class="table-scroll">
        <div class="user-row user-head"><span>用户</span><span>账号</span><span>角色</span><span>状态</span><span>最近登录</span><span>创建时间</span><span>操作</span></div>
        <div v-for="user in users" :key="user.id" class="user-row">
          <div class="user-cell"><span>{{ user.display_name.slice(0,1) }}</span><strong>{{ user.display_name }}</strong></div>
          <code>{{ user.username }}</code>
          <span>{{ roleNames[user.role] }}</span>
          <span class="state" :class="{ disabled: !user.is_active, locked: user.is_locked }"><i />{{ user.is_locked ? '已锁定' : user.is_active ? '已启用' : '已停用' }}</span>
          <div class="time-cell"><span>{{ formatTime(user.last_login_at) }}</span><small v-if="user.last_login_ip">{{ user.last_login_ip }}</small></div>
          <span>{{ formatTime(user.created_at) }}</span>
          <div class="actions"><button @click="openEdit(user)"><Pencil :size="14" />编辑</button><button @click="openPassword(user)"><KeyRound :size="14" />重置密码</button></div>
        </div>
        <div v-if="loading" class="empty"><LoaderCircle class="spin" :size="25" />正在读取用户</div>
        <div v-else-if="!users.length" class="empty"><UserRound :size="28" /><strong>没有符合条件的用户</strong><span>尝试调整筛选条件。</span></div>
      </div>
      <footer><span>共 {{ total }} 条</span><div><button :disabled="page <= 1" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button><b>{{ page }}</b><button :disabled="page >= pageCount" @click="changePage(page + 1)"><ChevronRight :size="16" /></button><small>{{ pageSize }} 条/页</small></div></footer>
    </article>

    <Teleport to="body">
      <div v-if="drawerOpen" class="drawer-layer" @mousedown.self="drawerOpen = false">
        <aside class="user-drawer" role="dialog" aria-modal="true">
          <header><div><small>{{ drawerMode === 'create' ? '创建平台访问账号' : drawerMode === 'edit' ? '更新账号与角色' : '生成新的登录凭据' }}</small><h3>{{ drawerMode === 'create' ? '新建用户' : drawerMode === 'edit' ? '编辑用户' : '重置密码' }}</h3></div><button @click="drawerOpen = false"><X :size="21" /></button></header>
          <form id="user-governance-form" @submit.prevent="save">
            <template v-if="drawerMode !== 'password'">
              <label><span>姓名 <b>*</b></span><input v-model.trim="form.display_name" required placeholder="请输入姓名" /></label>
              <label><span>登录账号 <b>*</b></span><input v-model.trim="form.username" :disabled="drawerMode === 'edit'" required pattern="[a-zA-Z][-a-zA-Z0-9_.]{2,63}" placeholder="例如：dispatcher01" /><small>以字母开头，可包含数字、点、下划线和连字符。</small></label>
              <label><span>角色 <b>*</b></span><select v-model="form.role"><option v-for="(label,key) in roleNames" :key="key" :value="key">{{ label }}</option></select></label>
            </template>
            <template v-if="drawerMode !== 'edit'">
              <label><span>{{ drawerMode === 'create' ? '初始密码' : '新密码' }} <b>*</b></span><div class="password-field"><input v-model="form.password" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" required /><button type="button" @click="showPassword = !showPassword"><EyeOff v-if="showPassword" :size="17" /><Eye v-else :size="17" /></button></div><small :class="{ invalid: form.password && !passwordValid }">至少 12 位，包含大小写字母、数字和特殊字符。</small></label>
              <label><span>确认密码 <b>*</b></span><div class="password-field"><input v-model="form.confirm_password" :type="showConfirm ? 'text' : 'password'" autocomplete="new-password" required /><button type="button" @click="showConfirm = !showConfirm"><EyeOff v-if="showConfirm" :size="17" /><Eye v-else :size="17" /></button></div><small v-if="form.confirm_password && form.password !== form.confirm_password" class="invalid">两次输入的密码不一致。</small></label>
            </template>
            <label v-if="drawerMode !== 'password'" class="switch-row"><div><strong>账号状态</strong><small>停用后用户不能登录，但审计记录会保留。</small></div><span><input v-model="form.is_active" type="checkbox" />启用</span></label>
            <label v-if="drawerMode === 'edit' && target?.is_locked" class="switch-row"><div><strong>解除登录锁定</strong><small>同时清空连续登录失败次数。</small></div><span><input v-model="form.unlock" type="checkbox" />解锁</span></label>
            <div v-if="drawerMode !== 'password'" class="permission-preview"><h4>权限预览（基于所选角色）</h4><div v-for="item in permissionMap[form.role]" :key="item[0]"><span>{{ item[0] }}</span><b>{{ item[1] }}</b></div></div>
            <div v-else class="security-callout"><ShieldCheck :size="19" /><p><b>安全操作</b><span>重置后原密码立即失效，同时解除该账号的登录锁定。密码不会写入审计日志。</span></p></div>
          </form>
          <footer><button class="cancel" :disabled="saving" @click="drawerOpen = false">取消</button><button class="save" form="user-governance-form" :disabled="saving || !canSave"><LoaderCircle v-if="saving" class="spin" :size="17" /><ShieldCheck v-else :size="17" />{{ drawerMode === 'create' ? '创建用户' : drawerMode === 'edit' ? '保存修改' : '确认重置' }}</button></footer>
        </aside>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.governance-page{display:flex;flex-direction:column;gap:18px;color:#22372d}.page-toolbar{display:flex;align-items:flex-start;justify-content:space-between}.page-toolbar h2{margin:0;font-size:25px}.page-toolbar p{margin:8px 0 0;color:#748178;font-size:13px}.primary{height:42px;display:flex;align-items:center;gap:8px;padding:0 16px;border:0;border-radius:8px;background:#0f6a45;color:#fff;font-weight:800;cursor:pointer}
.notice{display:flex;gap:8px;align-items:center;padding:11px 13px;border-radius:8px;font-size:13px}.notice.success{background:#edf7f1;border:1px solid #cce4d5;color:#136c46}.notice.error{background:#fff1f0;border:1px solid #edcecb;color:#a53e38}.notice button{margin-left:auto;border:0;background:transparent;color:inherit;cursor:pointer}
.summary-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.summary-strip article{display:flex;align-items:center;gap:14px;padding:17px 18px;border:1px solid #e0e6e2;border-radius:9px;background:#fff}.summary-strip article>span{width:40px;height:40px;display:grid;place-items:center;border-radius:50%;background:#f2f4f3;color:#283d32}.summary-strip article>span.green{background:#e9f6ee;color:#16754c}.summary-strip article>span.red{background:#fff0ef;color:#d7443d}.summary-strip small,.summary-strip strong{display:block}.summary-strip small{color:#748179;font-size:12px}.summary-strip strong{margin-top:3px;font-size:22px}
.user-table-card{overflow:hidden;border:1px solid #dfe5e1;border-radius:10px;background:#fff}.filter-bar{display:grid;grid-template-columns:minmax(220px,1fr) 170px 170px auto auto;gap:12px;padding:12px;border-bottom:1px solid #e5e9e6}.filter-bar input,.filter-bar select{height:40px;border:1px solid #d6ded9;border-radius:7px;background:#fff;padding:0 11px;font:inherit;font-size:13px;outline:none}.filter-bar input:focus,.filter-bar select:focus{border-color:#19784f;box-shadow:0 0 0 3px rgba(25,120,79,.1)}.search-field{position:relative}.search-field svg{position:absolute;left:12px;top:12px;color:#738178}.search-field input{width:100%;padding-left:38px}.filter-bar button{height:40px;border-radius:7px;padding:0 14px;font-weight:750;cursor:pointer}.query-button{border:0;background:#0f6a45;color:#fff}.reset-button{display:flex;align-items:center;gap:6px;border:1px solid #d5ddd8;background:#fff;color:#55675e}
.table-scroll{overflow-x:auto}.user-row{min-width:1040px;display:grid;grid-template-columns:1.12fr .85fr .8fr .75fr 1.15fr 1.05fr 1.35fr;align-items:center;gap:14px;min-height:67px;padding:0 17px;border-bottom:1px solid #e8ece9;font-size:13px}.user-row:hover:not(.user-head){background:#fafcfb}.user-head{min-height:42px;background:#f7f9f7;color:#69766f;font-size:12px;font-weight:800}.user-cell{display:flex;align-items:center;gap:10px}.user-cell>span{width:32px;height:32px;display:grid;place-items:center;border-radius:50%;background:#e7f2eb;color:#176e49;font-weight:800}.user-row code{color:#284839;font-size:12px}.state{width:max-content;display:flex;align-items:center;gap:6px;padding:5px 8px;border-radius:18px;background:#eaf6ef;color:#176f49;font-size:11px}.state i{width:6px;height:6px;border-radius:50%;background:#1b995f}.state.disabled{background:#f1f2f1;color:#707c75}.state.disabled i{background:#9aa39e}.state.locked{background:#fff0ef;color:#bf403a}.state.locked i{background:#e14841}.time-cell span,.time-cell small{display:block}.time-cell small{margin-top:4px;color:#8b958f;font-size:10px}.actions{display:flex;gap:3px}.actions button{height:32px;display:flex;align-items:center;gap:5px;border:0;border-radius:6px;padding:0 7px;background:transparent;color:#116e48;font-size:11px;cursor:pointer}.actions button:hover{background:#edf5f0}.empty{min-height:220px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;color:#7d8d84}.empty span{font-size:12px}.user-table-card>footer{display:flex;align-items:center;justify-content:space-between;padding:12px 17px;color:#748179;font-size:12px}.user-table-card footer div{display:flex;align-items:center;gap:7px}.user-table-card footer button,.user-table-card footer b{width:32px;height:32px;display:grid;place-items:center;border:1px solid #d7dfda;border-radius:6px;background:#fff;color:#52645a}.user-table-card footer b{border-color:#18744d;color:#147149}.user-table-card footer small{margin-left:5px}
.drawer-layer{position:fixed;inset:0;z-index:120;background:rgba(17,38,27,.36)}.user-drawer{position:absolute;right:0;top:0;width:min(500px,100%);height:100%;display:grid;grid-template-rows:auto 1fr auto;background:#fff;box-shadow:-14px 0 40px rgba(14,45,29,.14)}.user-drawer>header{height:78px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid #e1e6e3}.user-drawer header small{color:#7d8a82}.user-drawer h3{margin:4px 0 0;font-size:19px}.user-drawer header button{width:38px;height:38px;border:0;background:transparent;color:#637169;cursor:pointer}.user-drawer form{overflow-y:auto;padding:22px 24px;display:flex;flex-direction:column;gap:17px}.user-drawer form>label{display:flex;flex-direction:column;gap:7px}.user-drawer label>span{font-size:13px;font-weight:750}.user-drawer label b{color:#cb403a}.user-drawer input:not([type=checkbox]),.user-drawer select{width:100%;height:44px;border:1px solid #d6ded9;border-radius:8px;padding:0 12px;background:#fff;color:#273b30;font:inherit;outline:none}.user-drawer input:disabled{background:#f3f5f3;color:#77827c}.user-drawer input:focus,.user-drawer select:focus{border-color:#18784f;box-shadow:0 0 0 3px rgba(24,120,79,.1)}.user-drawer label small{color:#7e8b83;font-size:11px;line-height:1.5}.user-drawer label small.invalid{color:#b6423c}.password-field{position:relative}.password-field input{padding-right:43px!important}.password-field button{position:absolute;right:3px;top:3px;width:38px;height:38px;border:0;background:transparent;color:#718078;cursor:pointer}.switch-row{flex-direction:row!important;align-items:center;justify-content:space-between;padding:13px;border:1px solid #e0e6e2;border-radius:8px;background:#fafbfa}.switch-row strong,.switch-row small{display:block}.switch-row small{margin-top:4px}.switch-row>span{display:flex;align-items:center;gap:7px}.switch-row input{width:36px;height:20px;accent-color:#14774d}.permission-preview{padding:13px;border:1px solid #dfe5e1;border-radius:8px}.permission-preview h4{margin:0 0 9px;font-size:12px}.permission-preview div{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #edf0ee;font-size:12px}.permission-preview div b{color:#4f6559;font-weight:650}.security-callout{display:flex;gap:10px;padding:13px;border:1px solid #cce4d5;border-radius:8px;background:#eef8f2;color:#176c47}.security-callout p{margin:0}.security-callout b,.security-callout span{display:block}.security-callout span{margin-top:4px;color:#547467;font-size:11px;line-height:1.5}.user-drawer>footer{display:flex;justify-content:flex-end;gap:9px;padding:15px 24px;border-top:1px solid #e1e6e3}.user-drawer>footer button{height:42px;display:flex;align-items:center;gap:7px;padding:0 17px;border-radius:8px;font-weight:750;cursor:pointer}.cancel{border:1px solid #d4ddd7;background:#fff;color:#4f6258}.save{border:0;background:#0f6a45;color:#fff}.save:disabled{opacity:.5;cursor:not-allowed}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.password-field input::-ms-reveal{display:none}
@media(max-width:1000px){.summary-strip{grid-template-columns:repeat(2,1fr)}.filter-bar{grid-template-columns:1fr 1fr}.search-field{grid-column:1/-1}}@media(max-width:650px){.summary-strip{grid-template-columns:1fr}.page-toolbar{gap:16px;flex-direction:column}.primary{width:100%;justify-content:center}}
</style>
