<template>
  <div 
    class="min-h-screen w-full flex flex-col justify-between items-center relative select-none bg-cover bg-center py-6 px-4"
    style="background-image: url('/mockups/wuhan_city_pure.jpg');"
  >
    <!-- 背景柔和遮罩，确保卡片与城市背景层次分明 -->
    <div class="absolute inset-0 bg-slate-900/20 pointer-events-none"></div>

    <!-- 顶部占位 (保持居中平衡) -->
    <div class="h-4"></div>

    <!-- ── 核心居中登录卡片 (100% 还原风格 A 官方政务庄重质感) ── -->
    <div class="w-full max-w-[440px] bg-white rounded-2xl shadow-[0_12px_40px_rgba(0,0,0,0.18)] border border-slate-200/80 p-8 relative z-10 space-y-6">
      
      <!-- 顶部金色公安警徽与官方标题 -->
      <div class="flex flex-col items-center text-center space-y-2">
        <!-- 金色立体警徽标志 -->
        <div class="w-16 h-16 rounded-full flex items-center justify-center relative drop-shadow-md">
          <svg class="w-14 h-14" viewBox="0 0 100 100" fill="none">
            <!-- 警徽盾牌外形 -->
            <path d="M50 8 L85 24 V52 C85 74 50 92 50 92 C50 92 15 74 15 52 V24 Z" fill="url(#policeGold)" stroke="#d97706" stroke-width="2"/>
            <!-- 红色中心核心 -->
            <path d="M50 16 L78 29 V50 C78 68 50 82 50 82 C50 82 22 68 22 50 V29 Z" fill="#b91c1c"/>
            <!-- 金色五角星与长城麦穗纹样 -->
            <polygon points="50,26 54,38 66,38 56,46 60,58 50,50 40,58 44,46 34,38 46,38" fill="#fef08a" stroke="#ca8a04" stroke-width="0.8"/>
            <path d="M30 65 Q50 74 70 65" stroke="#fef08a" stroke-width="2.5" fill="none" stroke-linecap="round"/>
            <defs>
              <linearGradient id="policeGold" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#fef08a"/>
                <stop offset="50%" stop-color="#f59e0b"/>
                <stop offset="100%" stop-color="#b45309"/>
              </linearGradient>
            </defs>
          </svg>
        </div>

        <div>
          <h2 class="text-xl font-bold tracking-wide text-slate-900">武汉市公安局交通管理局</h2>
          <p class="text-sm font-medium text-slate-700 tracking-wide mt-1">非机动车交通违规综合治理平台</p>
        </div>
      </div>

      <!-- 快速免密身份通道 (答辩与一线人员快速登录) -->
      <div class="p-1 rounded-xl bg-slate-100 flex items-center gap-1 text-[13px] border border-slate-200">
        <button
          type="button"
          @click="selectPresetRole('officer')"
          class="flex-1 py-1.5 rounded-lg font-medium transition flex items-center justify-center gap-1.5"
          :class="selectedRole === 'officer' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'"
        >
          <el-icon :size="14"><User /></el-icon>
          <span>执勤执法人员</span>
        </button>
        <button
          type="button"
          @click="selectPresetRole('admin')"
          class="flex-1 py-1.5 rounded-lg font-medium transition flex items-center justify-center gap-1.5"
          :class="selectedRole === 'admin' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'"
        >
          <el-icon :size="14"><Setting /></el-icon>
          <span>系统管理员</span>
        </button>
        <button
          type="button"
          @click="selectPresetRole('citizen')"
          class="flex-1 py-1.5 rounded-lg font-medium transition flex items-center justify-center gap-1.5"
          :class="selectedRole === 'citizen' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'"
        >
          <el-icon :size="14"><Postcard /></el-icon>
          <span>市民</span>
        </button>
      </div>

      <!-- 登录表单 -->
      <form @submit.prevent="handleNormalLogin" class="space-y-4 text-xs">
        <!-- 警号/账号 -->
        <div class="space-y-1">
          <label class="block text-slate-700 font-medium">警号 / 警用账号</label>
          <div class="relative">
            <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
              <el-icon :size="15"><UserFilled /></el-icon>
            </span>
            <input 
              v-model="username" 
              type="text" 
              required
              placeholder="请输入 6 位执勤警号或管理员工号" 
              class="w-full h-10 pl-9 pr-3 rounded-lg border border-slate-300 text-slate-800 text-[13px] focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition" 
            />
          </div>
        </div>

        <!-- 密码 -->
        <div class="space-y-1">
          <label class="block text-slate-700 font-medium">系统访问密码</label>
          <div class="relative">
            <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
              <el-icon :size="15"><Lock /></el-icon>
            </span>
            <input 
              v-model="password" 
              :type="showPassword ? 'text' : 'password'" 
              required
              placeholder="请输入公安内网系统密码" 
              class="w-full h-10 pl-9 pr-10 rounded-lg border border-slate-300 text-slate-800 text-[13px] focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition" 
            />
            <button 
              type="button" 
              @click="showPassword = !showPassword"
              class="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition"
            >
              <el-icon :size="15"><component :is="showPassword ? 'View' : 'Hide'" /></el-icon>
            </button>
          </div>
        </div>

        <!-- 动态验证码 -->
        <div class="space-y-1">
          <label class="block text-slate-700 font-medium">警务动态验证码</label>
          <div class="flex items-center gap-2">
            <input 
              v-model="captchaInput" 
              type="text" 
              maxlength="4" 
              placeholder="输入 4 位验证码" 
              class="flex-1 h-10 px-3 rounded-lg border border-slate-300 text-slate-800 text-[13px] font-mono tracking-wider focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition" 
            />
            <!-- 防真扭曲防刷验证码卡片 -->
            <div 
              @click="refreshCaptcha" 
              class="h-10 px-3 bg-slate-100 border border-slate-300 rounded-lg flex items-center justify-center font-mono font-bold text-base tracking-widest text-blue-900 cursor-pointer select-none relative overflow-hidden"
              title="点击刷新验证码"
            >
              <span class="skew-x-6 scale-y-110">{{ captchaCode }}</span>
              <!-- 干扰线 -->
              <svg class="absolute inset-0 w-full h-full pointer-events-none opacity-40">
                <line x1="0" y1="10" x2="80" y2="30" stroke="#4f46e5" stroke-width="1.5" />
                <line x1="0" y1="35" x2="80" y2="5" stroke="#ef4444" stroke-width="1.5" />
              </svg>
            </div>
            <button 
              type="button" 
              @click="refreshCaptcha" 
              class="h-10 px-2.5 rounded-lg border border-slate-200 text-slate-500 hover:text-slate-800 text-xs transition"
              title="刷新验证码"
            >
              <el-icon :size="14"><Refresh /></el-icon>
            </button>
          </div>
        </div>

        <!-- U-Key PKI 证书认证通道 -->
        <button 
          type="button"
          @click="handleUKeyLogin"
          class="w-full h-9 rounded-lg border border-slate-300 hover:border-blue-400 bg-slate-50/60 hover:bg-slate-50 text-slate-700 text-xs font-medium transition flex items-center justify-center gap-1.5"
        >
          <el-icon :size="14"><Key /></el-icon>
          <span>U-Key PKI 数字证书免密登入</span>
        </button>

        <!-- 登录主按钮 -->
        <button 
          type="submit" 
          class="w-full h-11 rounded-lg bg-blue-700 hover:bg-blue-800 active:bg-blue-900 text-white font-medium text-[15px] transition shadow-md shadow-blue-700/25 flex items-center justify-center gap-1.5"
        >
          <span>登 录 系 统</span>
          <el-icon :size="16"><Right /></el-icon>
        </button>

        <div class="flex items-center justify-between text-slate-500 text-[11px] pt-1">
          <span class="hover:text-blue-600 cursor-pointer">忘记警务密码?</span>
          <span>技术内线: 8001 (交管科技科)</span>
        </div>
      </form>
    </div>

    <!-- ── 底栏政务版权与合规备案说明 ── -->
    <footer class="w-full text-center text-xs text-white/90 drop-shadow-[0_1px_4px_rgba(0,0,0,0.8)] py-2 space-y-1 z-10">
      <div class="flex items-center justify-center gap-4 text-[12px] opacity-90">
        <span class="hover:underline cursor-pointer">公安专网安全规定</span>
        <span>|</span>
        <span class="hover:underline cursor-pointer">数字防伪审计声明</span>
        <span>|</span>
        <span class="hover:underline cursor-pointer">联系交管支队</span>
      </div>
      <div class="font-mono text-[11px] opacity-80">
        © 2026 武汉市公安局交通管理局 · 智能非机动车视频分析实验室 版权所有
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getApiErrorMessage } from '../services/http'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

// 演示账号只在开发环境下预填；生产构建里一律留空，凭据必须由使用者自己输入。
const IS_DEV = import.meta.env.DEV
const DEMO_ACCOUNTS = {
  officer: { username: 'officer_zhang', password: '123456' },
  admin: { username: 'admin_super', password: 'admin888' },
  // 市民演示账号：绑定车牌由 backend/scripts/seed_citizen.py 写入
  citizen: { username: 'citizen_demo', password: '123456' }
}

const username = ref(IS_DEV ? DEMO_ACCOUNTS.officer.username : '')
const password = ref(IS_DEV ? DEMO_ACCOUNTS.officer.password : '')
const showPassword = ref(false)
const selectedRole = ref('officer')

const captchaInput = ref('')
const captchaCode = ref('')

function generateCaptcha() {
  const chars = '0123456789'
  let res = ''
  for (let i = 0; i < 4; i += 1) {
    res += chars[Math.floor(Math.random() * chars.length)]
  }
  captchaCode.value = res
}

// 刷新验证码只换题面并清空输入框。
// 之前这里会把答案自动填进输入框、还在提示里把答案念出来 —— 等于没校验。
function refreshCaptcha() {
  generateCaptcha()
  captchaInput.value = ''
}

// 选身份只切角色；只有开发环境才顺带把演示账号填进去。
function selectPresetRole(role) {
  selectedRole.value = role
  if (IS_DEV) {
    username.value = DEMO_ACCOUNTS[role].username
    password.value = DEMO_ACCOUNTS[role].password
  }
}

async function handleUKeyLogin() {
  // 真实 U-Key 证书校验需要后端与 PKI 支持，当前版本尚未接入。
  // 生产构建下如实告知，不做"假装插了证书"的成功提示。
  if (!IS_DEV) {
    ElMessage.warning('未检测到 U-Key 数字证书，请插入证书后重试，或改用账号密码登录')
    return
  }
  try {
    await authStore.login(DEMO_ACCOUNTS.officer.username, DEMO_ACCOUNTS.officer.password)
    ElMessage.success('【开发环境】模拟 U-Key 证书验证通过，自动登录')
    router.push('/history')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function handleNormalLogin() {
  if (!username.value.trim()) {
    ElMessage.warning('请输入警号 / 警用账号')
    return
  }
  if (!password.value) {
    ElMessage.warning('请输入系统访问密码')
    return
  }
  if (!captchaInput.value.trim()) {
    ElMessage.warning('请输入警务动态验证码')
    return
  }
  if (captchaInput.value.trim() !== captchaCode.value) {
    ElMessage.error('验证码不正确，请重新输入')
    refreshCaptcha()
    return
  }
  // 角色以后端返回的 user.role 为准，登录页的身份按钮只决定用哪个演示账号。
  try {
    await authStore.login(username.value.trim(), password.value)
    // 市民账号进群众端，执法账号进工作台——两边互不通行
    const isCitizen = authStore.currentUser?.role === 'citizen'
    ElMessage.success(
      isCitizen
        ? '登录成功，已进入公众服务端'
        : `欢迎回来，已以【${authStore.roleLabel}】身份登入交管平台！`
    )
    router.push(isCitizen ? '/citizen' : '/history')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
    refreshCaptcha()
  }
}

generateCaptcha()
</script>
