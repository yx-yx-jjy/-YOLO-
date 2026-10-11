<template>
  <div class="space-y-4">
    <!-- 顶部操作条 -->
    <div class="card flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">网络摄像头与实时流违规监测</h2>
        <p class="text-[12px] font-normal mt-0.5" style="color: var(--c-ink-3);">
          真实道路 RTSP 视频流 · 头盔状态智能识别 · 低延迟实时抓拍
        </p>
      </div>

      <div class="flex items-center gap-2 text-[13px]">
        <span class="text-[12px]" style="color: var(--c-ink-3);">卡口切换:</span>
        <select 
          v-model="selectedCam" 
          @change="onCamChange"
          class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none cursor-pointer"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
        >
          <option value="CAM-04">CAM-04: 武珞路-中南路口</option>
          <option value="CAM-03">CAM-03: 建设大道-香港路口</option>
          <option value="CAM-01">CAM-01: 珞喻路-光谷广场口</option>
          <option value="CAM-02">CAM-02: 解放大道-新华路口</option>
        </select>
        <button 
          @click="triggerSnap" 
          :disabled="isSnapping"
          class="h-8 px-3 rounded-md text-[13px] font-normal flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #334155;"
          @mouseenter="$event.currentTarget.style.borderColor = 'var(--c-primary)'; $event.currentTarget.style.color = 'var(--c-primary)'"
          @mouseleave="$event.currentTarget.style.borderColor = 'var(--c-line)'; $event.currentTarget.style.color = '#334155'"
        >
          <el-icon :size="14"><Camera /></el-icon>
          <span>{{ isSnapping ? '正在抓拍...' : '实时抓拍 (F8)' }}</span>
        </button>
        <button 
          @click="simulateViolation" 
          class="h-8 px-3 rounded-md text-[13px] font-normal flex items-center gap-1.5 transition cursor-pointer"
          style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: #B91C1C;"
          @mouseenter="$event.currentTarget.style.backgroundColor = '#FEF2F2'"
          @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-surface)'"
        >
          <el-icon :size="14"><Warning /></el-icon>
          <span>手动测试违规</span>
        </button>
      </div>
    </div>

    <!-- 监控主视图与右侧实时取证流 -->
    <MetricStrip :items="kpiItems" aria-label="实时监测概览" />

    <div class="grid grid-cols-12 gap-4">
      <!-- 监控画面 -->
      <div class="col-span-8">
        <div class="card space-y-3">
          <div class="flex items-center justify-between text-[12px] pb-2" style="border-bottom: 1px solid var(--c-line);">
            <div class="flex items-center gap-2">
              <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span class="font-mono font-medium" style="color: var(--c-ink-2);">
                {{ selectedCam }} | {{ streamStatus.width }}×{{ streamStatus.height }} @ {{ streamStatus.fps }} FPS
              </span>
            </div>
            <div class="flex items-center gap-4" style="color: var(--c-ink-2);">
              <label class="flex items-center gap-1.5 cursor-pointer select-none">
                <input type="checkbox" v-model="showHelmet" @change="refreshStream" class="rounded" style="accent-color: var(--c-primary)" />
                <span>头盔框</span>
              </label>
            </div>
          </div>

          <!-- 真实实时视频流画面 -->
          <div class="h-[460px] rounded-[10px] relative flex items-center justify-center overflow-hidden bg-slate-950">
            <!-- 实时视频流（MJPEG格式） -->
            <img 
              v-show="streamState === 'live'"
              :key="currentStreamUrl"
              :src="currentStreamUrl" 
              @load="onStreamLoaded"
              @error="onStreamError"
              class="w-full h-full object-contain select-none"
              alt="武汉道路实时监控流"
            />

            <!-- 连接中 -->
            <div v-if="streamState === 'connecting'" class="absolute inset-0 flex flex-col items-center justify-center text-slate-400 gap-2">
              <el-icon :size="28" class="is-loading"><Loading /></el-icon>
              <span class="text-[13px]">正在连接 {{ selectedCamTitle }} 实时视频流并启动检测引擎...</span>
            </div>

            <!-- 连接超时：给出原因和出口，不再无限转圈 -->
            <div v-else-if="streamState === 'timeout'" class="absolute inset-0 flex flex-col items-center justify-center gap-3 px-10 text-center">
              <el-icon :size="28" style="color: #F59E0B;"><Warning /></el-icon>
              <div>
                <div class="text-[13px]" style="color: #E2E8F0;">视频流连接超时</div>
                <div class="text-[12px] leading-5 mt-1" style="color: #94A3B8;">
                  分析任务占用资源时视频流可能延迟；也可先切换卡口再试
                </div>
              </div>
              <button
                @click="retryStream"
                class="h-8 px-3.5 rounded-md text-[13px] font-normal text-white"
                style="background-color: var(--c-primary);"
              >
                重新连接
              </button>
            </div>

            <!-- 浮动水印 (左上)：只在真正收到画面后显示，避免"没连上却报运行中" -->
            <div v-if="streamState === 'live'" class="absolute top-3 left-3 px-2.5 py-1 rounded font-mono text-[11px] flex items-center gap-1.5 shadow" style="background-color: rgba(15, 23, 42, 0.85); color: #E2E8F0; border: 1px solid rgba(255,255,255,0.1);">
              <span class="w-1.5 h-1.5 rounded-full" style="background-color: #10B981;"></span>
              <span>检测引擎运行中 · 延迟 {{ streamStatus.latency_ms ?? '—' }}ms · 检测到目标 {{ streamStatus.detections_count }}</span>
            </div>

            <!-- 浮动水印 (右下) -->
            <div class="absolute bottom-3 right-3 font-mono text-[11px] px-2.5 py-0.5 rounded shadow" style="background-color: rgba(15, 23, 42, 0.85); color: #94A3B8; border: 1px solid rgba(255,255,255,0.1);">
              {{ selectedCam }} | 武汉道路感知
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧抓拍记录：取自台账最新若干条，不是独立的实时推送流 -->
      <div class="col-span-4">
        <div class="card flex flex-col h-full space-y-3">
          <div class="flex items-center justify-between pb-2" style="border-bottom: 1px solid var(--c-line);">
            <h3 class="text-[14px] font-medium flex items-center gap-1.5" style="color: var(--c-ink);">
              <span class="w-1.5 h-1.5 rounded-full" style="background-color: #B45309;"></span>
              <span>最近抓拍记录</span>
            </h3>
            <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">台账最新 {{ displayRecords.length }} 条</span>
          </div>

          <div class="flex-1 space-y-2 overflow-y-auto max-h-[440px]">
            <div 
              v-for="item in displayRecords" 
              :key="item.id"
              @click="violationStore.openEvidenceModal(item)"
              class="p-3 rounded-md transition cursor-pointer group"
              style="border: 1px solid var(--c-line); background-color: var(--c-surface);"
              @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'; $event.currentTarget.style.borderColor = 'var(--c-primary)'"
              @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-surface)'; $event.currentTarget.style.borderColor = 'var(--c-line)'"
            >
              <div class="flex items-center justify-between">
                <span 
                  class="px-2 py-0.5 rounded text-[12px] font-medium whitespace-nowrap"
                  style="background-color: #FEF2F2; color: #B91C1C;"
                >
                  {{ item.violation_type }}
                </span>
                <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">
                  {{ (item.capture_time || '').slice(11, 19) }}
                </span>
              </div>
              <div class="text-[13px] font-normal mt-1.5 font-mono" style="color: var(--c-ink);">
                编号: {{ item.id }}
              </div>
              <div class="text-[12px] mt-0.5 font-normal" style="color: var(--c-ink-2);">
                目标: {{ item.details?.plate_or_vehicle || item.camera_id }}
              </div>
              <div class="text-[12px] font-normal mt-1.5 flex items-center justify-between" style="color: var(--c-primary);">
                <span>调取真实高清证据链 →</span>
                <span v-if="item.evidence_url" class="text-[11px] text-slate-400 font-mono">已存档</span>
              </div>
            </div>

            <EmptyState
              v-if="violationStore.recentError"
              compact
              variant="error"
              icon="WarningFilled"
              title="抓拍记录加载失败"
              description="无法从台账读取最新抓拍记录，请稍后重试或检查后端服务。"
              action-text="重试"
              @action="checkRecentViolations"
            />
            <EmptyState
              v-else-if="displayRecords.length === 0"
              compact
              icon="VideoCamera"
              title="暂无抓拍记录"
              description="保持实时流连接，系统连续确认违规后会自动生成待复核的抓拍记录。"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useViolationStore } from '../stores/violations'
import { 
  getCameraStreamUrl, 
  getCameraStatus, 
  triggerCameraSnapshot 
} from '../services/detectionApi'
import { ElMessage } from 'element-plus'
import { Camera, Warning, Loading } from '@element-plus/icons-vue'
import MetricStrip from '../components/MetricStrip.vue'
import EmptyState from '../components/EmptyState.vue'

const violationStore = useViolationStore()
const selectedCam = ref('CAM-03')
const showHelmet = ref(true)
const isSnapping = ref(false)
const streamToken = ref(Date.now())

const camTitles = {
  'CAM-04': 'CAM-04: 武珞路-中南路 (B站实景1080P)',
  'CAM-03': 'CAM-03: 建设大道-香港路口',
  'CAM-01': 'CAM-01: 珞喻路-光谷广场口',
  'CAM-02': 'CAM-02: 科技园区主干道卡口 (北向)',
  'LOCAL_USB': '本地 USB 高清摄像头 (0号设备)'
}

const selectedCamTitle = computed(() => camTitles[selectedCam.value] || selectedCam.value)

// 初始一律为 null：拿不到真实数据时显示"—"，不要用编好的数字假装已经连上
const streamStatus = ref({
  fps: null,
  latency_ms: null,
  width: null,
  height: null,
  detections_count: 0,
  violations_count: 0
})

// 视频流连接状态：connecting → live / timeout。
// 之前只有一个 isStreamLoaded 布尔值，连不上就无限转圈，用户无从判断是慢还是坏了。
const streamState = ref('connecting')
let streamTimer = null
// 后端恢复后自动补重连的次数上限：避免后端真的挂掉时无脑重试刷屏
const MAX_AUTO_RETRY = 2
let autoRetryCount = 0

function beginStreamWatch() {
  window.clearTimeout(streamTimer)
  streamState.value = 'connecting'
  streamTimer = window.setTimeout(() => {
    if (streamState.value === 'connecting') streamState.value = 'timeout'
  }, 15000)
}

function onStreamLoaded() {
  window.clearTimeout(streamTimer)
  streamState.value = 'live'
  autoRetryCount = 0 // 连上了就恢复自动重连额度
}

function onStreamError() {
  window.clearTimeout(streamTimer)
  if (streamState.value !== 'live') streamState.value = 'timeout'
}

// 用户主动点「重新连接」：视为一次全新尝试，额度重置
function retryStream() {
  autoRetryCount = 0
  streamToken.value = Date.now()
}

// 后端恢复后由轮询触发的补连：消耗额度，防止死循环
function autoRetryStream() {
  autoRetryCount += 1
  streamToken.value = Date.now()
}

const currentStreamUrl = computed(() => {
  return `${getCameraStreamUrl(selectedCam.value, showHelmet.value)}&token=${streamToken.value}`
})

// 串流地址一变（首次挂载、切换点位、手动重试）就重新计超时
watch(currentStreamUrl, () => beginStreamWatch())

const displayRecords = computed(() => {
  return violationStore.recentRecords.slice(0, 8)
})

// 概览条：实时链路指标 + 台账积压
const onlineCamCount = computed(() => Object.keys(camTitles).filter(key => key !== 'LOCAL_USB').length)

const kpiItems = computed(() => [
  {
    label: '在线卡口',
    value: onlineCamCount.value,
    unit: '处',
    tone: 'success'
  },
  {
    label: '实时视频帧率',
    value: streamStatus.value.fps,
    unit: streamStatus.value.fps == null ? '' : 'FPS',
    hint: streamStatus.value.fps == null ? '视频流未连接' : ''
  },
  {
    label: '端到端延迟',
    value: streamStatus.value.latency_ms,
    unit: streamStatus.value.latency_ms == null ? '' : 'ms',
    hint: streamStatus.value.latency_ms == null ? '视频流未连接' : ''
  },
  {
    label: '待人工复核',
    value: violationStore.pendingCount,
    unit: '起',
    tone: violationStore.pendingCount > 0 ? 'warning' : (violationStore.pendingCount == null ? 'default' : 'success')
  }
])

function onCamChange() {
  // 切点位是全新尝试：重置重连额度，并立刻回到 connecting，
  // 免得下面的 updateStatus() 拿上一轮的 timeout 误判成"需要补连"
  autoRetryCount = 0
  streamState.value = 'connecting'
  streamToken.value = Date.now()
  ElMessage.info(`正在切换至：${selectedCamTitle.value}`)
  updateStatus()
}

function refreshStream() {
  autoRetryCount = 0
  streamState.value = 'connecting'
  streamToken.value = Date.now()
}

async function updateStatus() {
  try {
    const data = await getCameraStatus(selectedCam.value)
    if (data) {
      streamStatus.value = { ...streamStatus.value, ...data }
      // 状态接口通了 => 后端是活的。此时如果视频流还卡在超时态，多半是
      // "后端重启过、但页面上的 <img> 不会自己重试"——浏览器只在标签页
      // 重建或 src 变化时才重发请求。这里自动补一次，用户不用手点。
      if (streamState.value === 'timeout' && autoRetryCount < MAX_AUTO_RETRY) {
        autoRetryStream()
      }
    }
  } catch (e) {
    // 后端不可达：静默等待，轮询会继续重试
  }
}

async function checkRecentViolations() {
  // 台账已由后端落库：这里直接刷新"最新抓拍"列表与摘要，不再往本地数组里塞记录
  await Promise.allSettled([
    violationStore.fetchRecentRecords(12),
    violationStore.fetchOverview()
  ])
}

async function triggerSnap() {
  if (isSnapping.value) return
  isSnapping.value = true
  try {
    const record = await triggerCameraSnapshot(selectedCam.value)
    await Promise.allSettled([
      violationStore.fetchRecentRecords(12),
      violationStore.fetchOverview()
    ])
    ElMessage.success({
      message: `实时抓拍成功！已保存高清证据帧 [${record.id}]`,
      duration: 3000
    })
  } catch (err) {
    ElMessage.error(`抓拍失败：${err.message || err}`)
  } finally {
    isSnapping.value = false
  }
}

function simulateViolation() {
  // 手动测试不再伪造记录，而是触发一次真实抓拍并写入台账
  ElMessage.warning('手动测试将触发一次实时抓拍并写入台账')
  triggerSnap()
}

function handleKeyDown(e) {
  if (e.key === 'F8') {
    e.preventDefault()
    triggerSnap()
  }
}

let statusTimer = null
let violationTimer = null

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  beginStreamWatch()
  updateStatus()
  checkRecentViolations()
  statusTimer = setInterval(updateStatus, 2000)
  violationTimer = setInterval(checkRecentViolations, 3000)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.clearTimeout(streamTimer)
  if (statusTimer) clearInterval(statusTimer)
  if (violationTimer) clearInterval(violationTimer)
})
</script>
