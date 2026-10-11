<template>
  <div class="min-h-screen flex text-[13px]" style="background-color: var(--c-page); color: var(--c-ink);">
    <!-- 左侧侧边栏 -->
    <aside class="w-60 flex flex-col justify-between flex-shrink-0 z-20" style="background-color: var(--c-nav-bg);">
      <div>
        <!-- 平台标识 -->
        <div class="h-14 px-5 flex items-center gap-3" style="border-bottom: 1px solid var(--c-nav-line);">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center text-white flex-shrink-0" style="background-color: var(--c-primary);">
            <ShieldMark :size="18" />
          </div>
          <div class="min-w-0">
            <h1 class="text-[14px] font-medium truncate" style="color: var(--c-nav-ink-strong);">交通违规监测</h1>
            <p class="text-[12px] truncate" style="color: var(--c-nav-ink-weak);">非机动车智能检测平台</p>
          </div>
        </div>

        <!-- 导航菜单：按业务域分组，避免 7 项平铺时分不出主次 -->
        <nav class="p-3 text-[13px]">
          <template v-for="(group, index) in navGroups" :key="group.title">
            <div
              class="px-3 pb-1.5 text-[12px] font-normal"
              :class="index === 0 ? 'pt-0.5' : 'pt-4'"
              style="color: var(--c-nav-ink-weak);"
            >
              {{ group.title }}
            </div>
            <div class="space-y-0.5">
              <router-link
                v-for="item in group.items"
                :key="item.to"
                :to="item.to"
                v-slot="{ isActive, navigate }"
                custom
              >
                <div
                  @click="navigate"
                  class="flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer relative"
                  :style="isActive
                    ? 'background-color: var(--c-nav-active-bg); color: var(--c-nav-active-ink);'
                    : 'color: var(--c-nav-ink);'"
                  @mouseenter="!isActive && ($event.currentTarget.style.backgroundColor = 'var(--c-nav-hover)')"
                  @mouseleave="!isActive && ($event.currentTarget.style.backgroundColor = '')"
                >
                  <span
                    v-if="isActive"
                    class="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-3.5 rounded-full"
                    style="background-color: var(--c-nav-active-ink);"
                  ></span>
                  <el-icon :size="18"><component :is="item.icon" /></el-icon>
                  <span class="font-medium">{{ item.label }}</span>
                  <!-- 待复核数徽章（仅检测历史） -->
                  <span
                    v-if="item.to === '/history' && violationStore.pendingCount > 0"
                    class="ml-auto px-1.5 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                    style="background-color: #FFFBEB; color: #B45309;"
                  >
                    {{ violationStore.pendingCount }}
                  </span>
                </div>
              </router-link>
            </div>
          </template>

          <!-- 管理员专区 -->
          <template v-if="authStore.isAdmin">
            <div class="pt-4 pb-1.5 px-3 text-[12px] font-normal" style="color: var(--c-nav-ink-weak);">
              系统控制台
            </div>
            <div class="space-y-0.5">
              <router-link
                v-for="item in adminNavItems"
                :key="item.to"
                :to="item.to"
                v-slot="{ isActive, navigate }"
                custom
              >
                <div
                  @click="navigate"
                  class="flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer relative"
                  :style="isActive
                    ? 'background-color: var(--c-nav-active-bg); color: var(--c-nav-active-ink);'
                    : 'color: var(--c-nav-ink);'"
                  @mouseenter="!isActive && ($event.currentTarget.style.backgroundColor = 'var(--c-nav-hover)')"
                  @mouseleave="!isActive && ($event.currentTarget.style.backgroundColor = '')"
                >
                  <span
                    v-if="isActive"
                    class="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-3.5 rounded-full"
                    style="background-color: var(--c-nav-active-ink);"
                  ></span>
                  <el-icon :size="18"><component :is="item.icon" /></el-icon>
                  <span class="font-medium">{{ item.label }}</span>
                </div>
              </router-link>
            </div>
          </template>
        </nav>
      </div>

      <!-- 侧边栏底部：用户信息 -->
      <div class="p-3" style="border-top: 1px solid var(--c-nav-line);">
        <div class="flex items-center justify-between mb-2 px-1">
          <div class="flex items-center gap-2 min-w-0">
            <div class="w-7 h-7 rounded-md text-white font-medium flex items-center justify-center text-[12px] flex-shrink-0" style="background-color: var(--c-primary);">
              {{ authStore.currentUser.real_name.slice(0, 1) }}
            </div>
            <div class="min-w-0">
              <div class="text-[13px] font-medium truncate" style="color: var(--c-nav-ink-strong);">{{ authStore.currentUser.real_name }}</div>
              <div class="text-[12px] truncate" style="color: var(--c-nav-ink-weak);">{{ authStore.roleLabel }}</div>
            </div>
          </div>
          <button
            @click="handleLogout"
            class="p-1.5 rounded-md flex-shrink-0"
            style="color: var(--c-nav-ink-weak);"
            title="退出系统"
            @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-nav-hover)'"
            @mouseleave="$event.currentTarget.style.backgroundColor = ''"
          >
            <el-icon :size="16"><SwitchButton /></el-icon>
          </button>
        </div>

        <!-- 身份切换是演示通道，只在开发环境出现；生产构建里没有"一键变管理员"这种后门 -->
        <button
          v-if="isDev"
          @click="authStore.switchRole(authStore.isAdmin ? 'officer' : 'admin')"
          class="w-full py-1.5 px-2.5 rounded-md text-[13px] font-normal flex items-center justify-center gap-1.5"
          style="background-color: var(--c-nav-hover); border: 1px solid var(--c-nav-line); color: var(--c-nav-ink);"
          @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-nav-active-ink)'; $event.currentTarget.style.color = 'var(--c-nav-active-ink)'"
          @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-nav-line)'; $event.currentTarget.style.color = 'var(--c-nav-ink)'"
        >
          <el-icon :size="14"><Refresh /></el-icon>
          <span>【演示】切换为: {{ authStore.isAdmin ? '执法人员' : '系统管理员' }}</span>
        </button>
      </div>
    </aside>

    <!-- 右侧主体 -->
    <div class="flex-1 flex flex-col min-w-0 overflow-y-auto">
      <!-- 顶栏 -->
      <header class="h-14 bg-white px-6 flex items-center justify-between sticky top-0 z-10" style="border-bottom: 1px solid var(--c-line);">
        <div>
          <div class="flex items-center gap-1.5 text-[12px]" style="color: var(--c-ink-3);">
            <span>交通违规监测系统</span>
            <span>/</span>
            <span style="color: var(--c-primary);" class="font-medium">{{ currentRouteTitle }}</span>
          </div>
          <div class="text-[13px] font-medium mt-0.5" style="color: var(--c-ink);">{{ currentRouteSub }}</div>
        </div>

        <div class="flex items-center gap-3 text-[12px]">
          <div class="flex items-center gap-1.5 px-2.5 py-1 rounded-md font-normal" style="background-color: var(--c-page); color: var(--c-ink-2); border: 1px solid var(--c-line);">
            <span
              class="w-1.5 h-1.5 rounded-full"
              :style="{ backgroundColor: modelReady === null ? '#94A3B8' : (modelReady ? '#15803D' : '#D97706') }"
            ></span>
            <span class="font-mono">{{ modelStatusText }}</span>
          </div>

          <!-- 待办中心：把"现在该处理什么"收在一个入口里 -->
          <el-popover placement="bottom-end" :width="304" trigger="click">
            <template #reference>
              <button
                class="relative p-1.5 rounded-md"
                style="color: var(--c-ink-2); border: 1px solid var(--c-line);"
                title="待办与系统状态"
              >
                <el-icon :size="16"><Bell /></el-icon>
                <span
                  v-if="todoTotal > 0"
                  class="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full text-[11px] leading-4 text-center text-white"
                  style="background-color: #B91C1C;"
                >
                  {{ todoTotal }}
                </span>
              </button>
            </template>

            <div class="space-y-2">
              <div class="text-[13px] font-medium" style="color: var(--c-ink);">待办与系统状态</div>
              <button
                v-for="item in todoItems"
                :key="item.key"
                class="w-full flex items-center justify-between gap-2 px-2.5 py-2 rounded-md text-left"
                style="border: 1px solid var(--c-line); background-color: var(--c-surface);"
                @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'"
                @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'"
                @click="goTodo(item)"
              >
                <span class="flex items-center gap-2 text-[13px] font-normal" style="color: var(--c-ink-2);">
                  <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ backgroundColor: item.color }"></span>
                  <span>{{ item.label }}</span>
                </span>
                <span class="font-mono text-[13px] font-medium whitespace-nowrap" :style="{ color: item.color }">
                  {{ item.value }}
                </span>
              </button>
              <div class="text-[12px] font-normal" style="color: var(--c-ink-3); line-height: 18px;">
                点击任一项跳转到对应页面处理。待办数字来自台账实时统计。
              </div>
            </div>
          </el-popover>

          <button
            @click="goToScreen"
            class="h-7 px-2.5 rounded-md text-[12px] font-normal flex items-center gap-1.5 transition"
            style="background-color: var(--c-primary-weak); color: var(--c-primary); border: 1px solid var(--c-primary);"
            title="进入全屏综合态势大屏"
          >
            <el-icon :size="13"><Monitor /></el-icon>
            <span>态势大屏</span>
          </button>
          <button
            @click="refreshEngineStatus()"
            :disabled="statusProbing"
            class="p-1.5 rounded-md disabled:opacity-50"
            style="color: var(--c-ink-2); border: 1px solid var(--c-line);"
            :title="statusProbing ? '正在重新探测检测引擎…' : '重新探测检测引擎状态'"
            @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
            @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = 'var(--c-ink-2)'"
          >
            <el-icon :size="16"><Refresh /></el-icon>
          </button>
        </div>
      </header>

      <!-- 页面渲染区 -->
      <main class="flex-1 py-5 px-6">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- 全局证据模态框 -->
    <EvidenceModal />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useViolationStore } from '../stores/violations'
import { ElMessage } from 'element-plus'
import EvidenceModal from '../components/EvidenceModal.vue'
import { getInferenceHealth } from '../services/detectionApi'
import ShieldMark from '../components/ShieldMark.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const violationStore = useViolationStore()

// 身份切换按钮是演示通道，只在开发环境显示
const isDev = import.meta.env.DEV

// 引擎状态初始为 null：探测出来之前显示「探测中」，不假装已就绪
const modelReady = ref(null)
const statusProbing = ref(false)

const modelStatusText = computed(() => {
  if (modelReady.value === null) return '检测引擎 · 探测中'
  return modelReady.value ? '检测引擎 · 已就绪' : '检测引擎 · 未就绪'
})

// 按业务域分组：识别 → 复核研判 → 模型系统，避免 7 项平铺时主次不分
const navGroups = [
  {
    title: '实时监测',
    items: [
      { to: '/image', label: '图片识别', icon: 'Picture' },
      { to: '/video', label: '视频识别', icon: 'VideoPlay' },
      { to: '/camera', label: '摄像头识别', icon: 'VideoCamera' }
    ]
  },
  {
    title: '复核与研判',
    items: [
      { to: '/history', label: '检测历史与复核', icon: 'Document' },
      { to: '/analysis', label: '数据研判与预测', icon: 'TrendCharts' }
    ]
  },
  {
    title: '模型与系统',
    items: [
      { to: '/model', label: '模型管理与原理', icon: 'Setting' },
      { to: '/metrics', label: '指标展示', icon: 'DataLine' }
    ]
  }
]

/* ── 待办中心：数字全部来自 /api/stats/overview 与引擎探测，不写死 ── */
const lowConfidenceCount = computed(() => violationStore.lowConfidenceCount)

const todoItems = computed(() => {
  const pending = violationStore.pendingCount
  const lowConfidence = lowConfidenceCount.value
  const pendingDisposition = violationStore.pendingDispositionCount
  return [
    {
      key: 'pending',
      label: '待人工复核',
      value: pending ?? '—',
      color: pending > 0 ? '#B45309' : '#15803D',
      to: '/history',
      query: { status: 'pending' }
    },
    {
      key: 'low',
      label: '其中低置信线索 (< 70%)',
      value: lowConfidence ?? '—',
      color: lowConfidence > 0 ? '#B91C1C' : '#15803D',
      to: '/history',
      query: { status: 'pending', band: 'low' }
    },
    {
      key: 'disposition',
      label: '待告知 / 待处理',
      value: pendingDisposition ?? '—',
      color: pendingDisposition > 0 ? '#B45309' : '#15803D',
      to: '/history',
      query: { status: 'approved', disposition: 'to_notify' }
    },
    {
      key: 'engine',
      label: '检测引擎',
      value: modelReady.value === null ? '探测中' : (modelReady.value ? '就绪' : '未就绪'),
      color: modelReady.value === true ? '#15803D' : (modelReady.value === null ? '#94A3B8' : '#B45309'),
      to: '/model',
      query: {}
    }
  ]
})

// 待办 = 待复核 + 待处置：复核完不算完，处置没走完同样是"该处理的事"
const todoTotal = computed(() =>
  (violationStore.pendingCount ?? 0) + (violationStore.pendingDispositionCount ?? 0)
)

function goTodo(item) {
  router.push({ path: item.to, query: item.query })
}

const adminNavItems = [
  { to: '/admin/users', label: '账号管理', icon: 'User' },
  { to: '/admin/logs', label: '审计日志', icon: 'Tickets' }
]

const routeMap = {
  '/image': { title: '图片识别', sub: '静态交通照片单帧与批量违规检测' },
  '/video': { title: '视频识别', sub: '离线道路卡口监控视频智能分析' },
  '/camera': { title: '摄像头识别', sub: '实时视频流监测与违规捕获' },
  '/history': { title: '检测历史与复核', sub: '违规事件台账与人工复核' },
  '/analysis': { title: '数据研判与预测', sub: '卡口时空违规统计与未来高危时段 AI 预警' },
  '/model': { title: '模型管理与原理', sub: '识别模型配置与性能指标' },
  '/metrics': { title: '指标展示', sub: '训练曲线与性能汇总' },
  '/admin/users': { title: '账号管理', sub: '执法人员账号创建与授权' },
  '/admin/logs': { title: '系统审计日志', sub: '操作溯源流水' }
}

const currentRouteTitle = computed(() => routeMap[route.path]?.title || '监控工作台')
const currentRouteSub = computed(() => routeMap[route.path]?.sub || '系统运行正常')

/**
 * 重新探测检测引擎状态。
 * 之前这里只弹一句"已刷新最新检测状态"，其实什么都没做 ——
 * 状态点永远是页面挂载时那一次的结果，失败后永久置灰。
 * 现在真的重新请求 /api/health，并把结果如实反映到状态点与文案上。
 */
async function refreshEngineStatus(silent = false) {
  if (statusProbing.value) return
  statusProbing.value = true
  try {
    const health = await getInferenceHealth()
    modelReady.value = health.model?.ready === true
    if (!silent) {
      ElMessage.success(
        modelReady.value
          ? '已重新探测检测引擎：服务就绪'
          : '已重新探测：服务在线，但模型尚未加载'
      )
    }
  } catch {
    modelReady.value = false
    if (!silent) {
      ElMessage.warning('未能连接检测引擎，请确认后端服务已启动（127.0.0.1:8000）')
    }
  } finally {
    statusProbing.value = false
  }
}

function goToScreen() {
  router.push('/screen')
}

function handleLogout() {
  authStore.logout()
  ElMessage.info('已安全退出交管违规监测平台')
  router.push('/login')
}

onMounted(() => {
  refreshEngineStatus(true)
  // 侧边栏待办徽章与待办中心都依赖摘要统计，进入工作台时先拉一次
  violationStore.fetchOverview()
})
</script>
