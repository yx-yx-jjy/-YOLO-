<template>
  <div class="h-screen w-full overflow-hidden flex flex-col bg-[#070C18] text-slate-100 font-sans select-none relative box-border">
    <!-- 背景流光与微弱科技网格 -->
    <div class="absolute inset-0 bg-[linear-gradient(to_right,#111C35_1px,transparent_1px),linear-gradient(to_bottom,#111C35_1px,transparent_1px)] bg-[size:3rem_3rem] opacity-20 pointer-events-none"></div>
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-2/3 h-28 bg-cyan-500/10 blur-[80px] pointer-events-none"></div>

    <!-- 顶部科技 HUD 标题栏 -->
    <header class="h-14 relative flex items-center justify-between px-5 border-b border-cyan-900/40 bg-[#0A1224]/90 backdrop-blur-md z-20 flex-shrink-0">
      <!-- 左侧：系统时间与状态 -->
      <div class="flex items-center gap-3 text-xs font-mono text-cyan-400/90 flex-shrink-0">
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="text-slate-300">武汉交警智能视频分析中心</span>
        </div>
        <span class="text-slate-600">|</span>
        <span class="text-slate-400 text-[11px]">{{ currentTimeStr }}</span>
      </div>

      <!-- 中间：大屏主标题 -->
      <div class="flex-1 flex flex-col items-center justify-center px-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-0.5 bg-gradient-to-r from-transparent to-cyan-400"></div>
          <h1 class="text-lg font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-b from-white via-cyan-100 to-cyan-400 drop-shadow-[0_2px_10px_rgba(6,182,212,0.4)] whitespace-nowrap">
            武汉市非机动车交通违规态势综合监测指挥大屏
          </h1>
          <div class="w-10 h-0.5 bg-gradient-to-l from-transparent to-cyan-400"></div>
        </div>
        <div class="text-[11px] font-mono tracking-widest text-cyan-400/60 uppercase">
          Wuhan Traffic Police · Smart Vision & Violation Heatmap Surveillance
        </div>
      </div>

      <!-- 右侧：快捷返回与全屏控制 -->
      <div class="flex items-center justify-end gap-2.5 text-xs flex-shrink-0">
        <div class="px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/40 text-cyan-300 text-[11px] font-mono flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full animate-ping" :class="engineFps ? 'bg-emerald-400' : 'bg-slate-500'"></span>
          <span>感知引擎: {{ engineFps ? `${engineFps} FPS` : '未连接' }}</span>
        </div>
        <button 
          @click="toggleFullScreen"
          class="h-7 px-2.5 rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-200 transition flex items-center gap-1 text-[11px]"
          title="全屏切换"
        >
          <el-icon :size="13"><FullScreen /></el-icon>
          <span>{{ isFull ? '退出全屏' : '全屏' }}</span>
        </button>
        <button 
          @click="returnToAdmin"
          class="h-7 px-3 rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-200 transition flex items-center gap-1.5 text-[11px]"
          title="结束大屏演示，返回管理工作台"
        >
          <el-icon :size="13"><Back /></el-icon>
          <span>返回工作台</span>
        </button>
      </div>
    </header>

    <!-- 主体栅格布局 -->
    <main class="flex-1 p-3 grid grid-cols-12 gap-3 min-h-0 w-full overflow-hidden box-border relative z-10">
      
      <!-- ── 左侧面板 (3 列)：核心指标、24小时潮汐、违规走势 ── -->
      <section class="col-span-3 flex flex-col gap-2.5 min-h-0">
        <!-- 1. 今日统计大卡片 -->
        <div class="p-3 rounded-xl bg-[#0C152B]/90 border border-cyan-900/40 flex flex-col gap-2 shadow-lg relative overflow-hidden flex-shrink-0">
          <div class="text-xs text-cyan-300/80 font-medium flex items-center justify-between">
            <span class="flex items-center gap-1.5">
              <el-icon><DataAnalysis /></el-icon>
              <span>今日新增违规线索</span>
            </span>
            <span class="text-[11px] font-mono text-cyan-400/60">由台账实时派生</span>
          </div>
          <div class="flex items-baseline gap-1.5">
            <span class="text-2xl font-bold font-mono text-cyan-300 tracking-tight drop-shadow-[0_0_12px_rgba(6,182,212,0.4)]">
              {{ todayTotal == null ? '—' : todayTotal.toLocaleString() }}
            </span>
            <span class="text-xs text-slate-400">起</span>
          </div>

          <!-- 4 宫格小指标：取自 /api/stats/overview，与「检测历史与复核」页同源 -->
          <div class="grid grid-cols-2 gap-1.5 pt-1 border-t border-slate-800/80">
            <div class="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-slate-400">待人工复核</div>
              <div class="text-sm font-bold font-mono text-amber-400 mt-0.5">{{ stat(reviewPanel.pending) }} <span class="text-[11px] font-normal text-slate-400">起</span></div>
            </div>
            <div class="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-slate-400">已确认入卷</div>
              <div class="text-sm font-bold font-mono text-emerald-400 mt-0.5">{{ stat(reviewPanel.approved) }} <span class="text-[11px] font-normal text-slate-400">起</span></div>
            </div>
            <div class="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-slate-400">误报已剔除</div>
              <div class="text-sm font-bold font-mono text-slate-300 mt-0.5">{{ stat(reviewPanel.rejected) }} <span class="text-[11px] font-normal text-slate-400">起</span></div>
            </div>
            <div class="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-slate-400">平均置信度</div>
              <div class="text-sm font-bold font-mono text-cyan-400 mt-0.5">{{ avgConfidence === null ? '—' : `${avgConfidence}%` }}</div>
            </div>
          </div>
        </div>

        <!-- 2. 逐小时骑行与违规潮汐 (柱状图) -->
        <div class="flex-1 p-2.5 rounded-xl bg-[#0C152B]/90 border border-cyan-900/40 flex flex-col shadow-lg min-h-0">
          <div class="text-xs text-cyan-300 font-medium flex items-center justify-between pb-1 border-b border-slate-800/80">
            <span>24小时违规潮汐时序</span>
            <span class="text-[11px] font-mono text-slate-400">早晚高峰分布</span>
          </div>
          <div v-if="hourlyError" class="flex-1 flex items-center justify-center text-[11px]" style="color: #64748B;">数据不可用</div>
          <div v-else ref="hourlyChartRef" class="flex-1 w-full min-h-0"></div>
        </div>

        <!-- 3. 未戴头盔趋势 -->
        <div class="flex-1 p-2.5 rounded-xl bg-[#0C152B]/90 border border-cyan-900/40 flex flex-col shadow-lg min-h-0">
          <div class="text-xs text-cyan-300 font-medium flex items-center justify-between pb-1 border-b border-slate-800/80">
            <span>未戴头盔线索走势</span>
            <span class="text-[11px] font-mono text-slate-400">近 7 天走势</span>
          </div>
          <div v-if="weeklyError" class="flex-1 flex items-center justify-center text-[11px]" style="color: #64748B;">数据不可用</div>
          <div v-else ref="trendChartRef" class="flex-1 w-full min-h-0"></div>
        </div>
      </section>

      <!-- ── 中间主视窗 (6 列)：武汉电子地图与违规热力投影 + 底部实时流水 ── -->
      <section class="col-span-6 flex flex-col gap-2.5 min-h-0">
        <!-- 武汉两江电子地图 -->
        <div class="flex-1 rounded-xl bg-[#0A1224] border border-cyan-800/50 p-2.5 flex flex-col relative overflow-hidden shadow-2xl min-h-0">
          <!-- 地图上浮操作条 -->
          <div class="flex items-center justify-between z-10 mb-1.5 flex-shrink-0">
            <!-- 图层切换 -->
            <div class="flex items-center gap-1 bg-slate-900/90 p-0.5 rounded-lg border border-slate-800 text-xs">
              <button 
                v-for="layer in layers" :key="layer.key"
                @click="activeLayer = layer.key"
                class="px-2.5 py-1 rounded transition text-[11px]"
                :class="activeLayer === layer.key ? 'bg-cyan-600 text-white font-medium' : 'text-slate-400 hover:text-slate-200'"
              >
                {{ layer.name }}
              </button>
            </div>

            <!-- 武汉卡口选择 -->
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-400 font-mono">监控卡口:</span>
              <select 
                v-model="activeCam" 
                class="bg-slate-900/90 border border-slate-700 rounded-lg px-2 py-1 text-xs text-cyan-300 font-mono focus:outline-none focus:border-cyan-500"
              >
                <option value="ALL">全市卡口总览</option>
                <option value="CAM-03">汉口 · 建设大道-香港路口 (金融街)</option>
                <option value="CAM-01">武昌 · 珞喻路-光谷广场口 (光谷)</option>
                <option value="CAM-02">汉口 · 解放大道-新华路口 (中山公园)</option>
                <option value="CAM-04">武昌 · 武珞路-中南路口 (中南商圈)</option>
                <option value="CAM-05">汉阳 · 钟家村-鹦鹉大道口 (汉阳枢纽)</option>
              </select>
            </div>
          </div>

          <!-- 高德地图武汉真实路网（原色 / 融合 / 深色三档底图，默认融合） -->
          <div
            class="flex-1 relative rounded-lg overflow-hidden min-h-0 border transition-colors duration-200"
            :class="basemap === 'dark'
              ? 'bg-[#060B16] border-slate-800/80'
              : 'bg-[#0A1224] border-slate-600/60 ring-1 ring-inset ring-cyan-400/10'"
          >
            <WuhanTrafficMap
              v-model:active-cam="activeCam"
              v-model:basemap="basemap"
              :active-layer="activeLayer"
            />
          </div>

        </div>

        <!-- ── 底部横向跑马灯：实时违规抓拍取证流水 (高度增加，彻底解决文字截断) ── -->
        <div class="h-36 rounded-xl bg-[#0C152B]/90 border border-cyan-900/40 p-2.5 flex flex-col shadow-lg flex-shrink-0 overflow-hidden box-border">
          <div class="text-[11px] text-cyan-300/80 font-medium flex items-center justify-between pb-1 flex-shrink-0">
            <span class="flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>
              <span>实时抓拍电子取证证据链 (最新检测记录动态滚动)</span>
            </span>
            <span class="text-[11px] font-mono text-slate-500">点击卡片可即时复核</span>
          </div>

          <!-- 横向卡片容器：优化高度与内边距，文字绝不挤压重合 -->
          <div class="flex-1 flex gap-2.5 overflow-x-auto items-center py-1 style-scrollbar">
            <div 
              v-for="record in violationStore.recentRecords.slice(0, 12)" 
              :key="record.id"
              @click="openEvidence(record)"
              class="h-[88px] min-w-[240px] px-3 py-2 rounded-lg bg-slate-900/90 border border-slate-800 hover:border-cyan-500 transition cursor-pointer flex flex-col justify-between flex-shrink-0"
            >
              <!-- 顶部行：编号 + 状态 -->
              <div class="flex items-center justify-between text-[11px] leading-tight">
                <span class="font-mono text-cyan-400 font-medium">{{ record.id.slice(12) }}</span>
                <span 
                  class="px-1.5 py-0.2 rounded text-[11px] font-normal" 
                  :class="record.status === 'pending' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'"
                >
                  {{ record.status === 'pending' ? '待复核' : '已入卷' }}
                </span>
              </div>

              <!-- 中间行：违规行为名称 (字号舒适，独立占行，绝不与底部挤压) -->
              <div class="text-[12px] font-medium text-slate-100 truncate py-0.5" :title="record.violation_type">
                {{ formatViolationType(record.violation_type) }}
              </div>

              <!-- 底部行：监控点位与算法置信度 -->
              <div class="flex items-center justify-between text-[11px] text-slate-400 font-mono leading-tight border-t border-slate-800/80 pt-1">
                <span class="truncate max-w-[130px]">{{ record.camera_id }}</span>
                <span class="text-cyan-400 font-medium">置信 {{ (record.confidence * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ── 右侧面板 (3 列)：类型占比、高危路口 TOP5、设备运行 ── -->
      <section class="col-span-3 flex flex-col gap-2.5 min-h-0">
        <!-- 1. 违规类型占比 (环形饼图) -->
        <div class="p-2.5 rounded-xl bg-[#0C152B]/90 border border-cyan-900/40 flex flex-col shadow-lg h-[200px] flex-shrink-0">
          <div class="text-xs text-cyan-300 font-medium flex items-center justify-between pb-1 border-b border-slate-800/80">
            <span>违规行为类别构成占比</span>
            <span class="text-[11px] font-mono text-slate-400">今日总计 {{ stat(todayTotal) }} 起</span>
          </div>
          <div v-if="overviewError" class="flex-1 flex items-center justify-center text-[11px]" style="color: #64748B;">数据不可用</div>
          <div v-else ref="pieChartRef" class="flex-1 w-full min-h-0"></div>
        </div>

        <!-- 2. 高频违规路口 TOP5 排名 -->
        <div class="flex-1 p-2.5 rounded-xl bg-[#0C152B]/90 border border-cyan-900/40 flex flex-col shadow-lg min-h-0">
          <div class="text-xs text-cyan-300 font-medium flex items-center justify-between pb-1 border-b border-slate-800/80">
            <span>武汉高发卡口 TOP5 排名</span>
            <span class="text-[11px] font-mono text-slate-400">今日抓拍频次</span>
          </div>
          <div class="flex-1 flex flex-col justify-around py-1">
            <div v-if="byCameraError" class="text-center text-[11px]" style="color: #64748B;">数据不可用</div>
            <div v-else-if="topSpots.length === 0" class="text-center text-[11px]" style="color: #64748B;">近 24 小时暂无抓拍</div>
            <template v-else>
              <div v-for="(item, index) in topSpots" :key="item.name" class="space-y-0.5">
                <div class="flex items-center justify-between text-[11px]">
                  <div class="flex items-center gap-1.5 truncate">
                    <span 
                      class="w-3.5 h-3.5 rounded text-[11px] font-mono font-bold flex items-center justify-center"
                      :class="index === 0 ? 'bg-rose-600 text-white' : index === 1 ? 'bg-amber-600 text-white' : index === 2 ? 'bg-cyan-600 text-white' : 'bg-slate-800 text-slate-400'"
                    >
                      {{ index + 1 }}
                    </span>
                    <span class="text-slate-200 truncate">{{ item.name }}</span>
                  </div>
                  <span class="font-mono text-cyan-300 text-[11px] font-bold">{{ item.count }}起</span>
                </div>
                <div class="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div 
                    class="h-full rounded-full transition-all duration-500"
                    :style="{ 
                      width: item.percent + '%',
                      backgroundColor: index === 0 ? '#f43f5e' : index === 1 ? '#f59e0b' : '#06b6d4'
                    }"
                  ></div>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- 3. 台账复核进度（与「检测历史与复核」页同源，不再是编造的探头工况） -->
        <div class="p-2.5 rounded-xl bg-[#0C152B]/90 border border-cyan-900/40 flex flex-col shadow-lg flex-shrink-0">
          <div class="text-xs text-cyan-300 font-medium pb-1.5 border-b border-slate-800/80 flex items-center justify-between">
            <span>台账复核进度</span>
            <span class="text-[11px] font-mono text-cyan-400">共 {{ stat(reviewPanel.total) }} 起 · 已处理 {{ stat(reviewPanel.rate) }}%</span>
          </div>
          <div class="grid grid-cols-4 gap-1.5 pt-1.5 text-center">
            <div class="p-1 rounded bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-amber-400">待复核</div>
              <div class="text-xs font-bold font-mono text-amber-400 mt-0.5">{{ stat(reviewPanel.pending) }}</div>
            </div>
            <div class="p-1 rounded bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-emerald-400">已入卷</div>
              <div class="text-xs font-bold font-mono text-emerald-400 mt-0.5">{{ stat(reviewPanel.approved) }}</div>
            </div>
            <div class="p-1 rounded bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-slate-400">误报剔除</div>
              <div class="text-xs font-bold font-mono text-slate-300 mt-0.5">{{ stat(reviewPanel.rejected) }}</div>
            </div>
            <div class="p-1 rounded bg-slate-900/60 border border-slate-800">
              <div class="text-[11px] text-rose-400">低置信线索</div>
              <div class="text-xs font-bold font-mono text-rose-400 mt-0.5">{{ stat(reviewPanel.lowConfidence) }}</div>
            </div>
          </div>
        </div>
      </section>

    </main>

    <!-- 弹出的证据复核模态框 -->
    <EvidenceModal />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useViolationStore } from '../stores/violations'
import * as echarts from 'echarts'
import EvidenceModal from '../components/EvidenceModal.vue'
import WuhanTrafficMap from '../components/WuhanTrafficMap.vue'
import { cameraName } from '../data/cameras'
import { getCameraStatus } from '../services/detectionApi'
import { fetchOverview, fetchTimeseries, fetchByCamera } from '../services/statsApi'

const router = useRouter()
const violationStore = useViolationStore()

const currentTimeStr = ref('')
const isFull = ref(false)

const activeLayer = ref('all')
const activeCam = ref('ALL')
// 大屏默认"融合"底图：真实路网降噪压暗后融进深色基调；可切原色 / 深色
const basemap = ref('blend')

// 引擎帧率取后端真实值；拿不到就显示「—」，不用编好的数字假装在跑
const engineFps = ref(null)

const layers = [
  { key: 'all', name: '全图层' },
  { key: 'heatmap', name: '违规热力' },
  { key: 'cams', name: '抓拍卡口' }
]

const hourlyChartRef = ref(null)
const trendChartRef = ref(null)
const pieChartRef = ref(null)

let charts = []
let timeTimer = null
let statusTimer = null
let statsTimer = null

/* ── 统计接口：单个接口失败只让对应卡片显示「数据不可用」，其余照常渲染 ── */
const overview = ref(null)
const overviewError = ref(false)
const hourly = ref(null)
const hourlyError = ref(false)
const weekly = ref(null)
const weeklyError = ref(false)
const byCamera = ref(null)
const byCameraError = ref(false)

/** 未就绪时显示「—」，不假装是 0 */
function stat(value) {
  return value === null || value === undefined ? '—' : value
}

// 「今日」口径取 overview.today_total（后端按 date 分日统计）；
// overview.total / status / disposition 是全量累计口径，不能拿来当"今日"。
const todayTotal = computed(() => (
  overview.value ? (overview.value.today_total ?? overview.value.total) : null
))

// avg_confidence 口径未在契约中明确，兼容 0~1 与 0~100 两种
const avgConfidence = computed(() => {
  const raw = overview.value?.avg_confidence
  if (raw === null || raw === undefined) return null
  return raw <= 1 ? Math.round(raw * 100) : Math.round(raw)
})

const reviewPanel = computed(() => ({
  pending: overview.value ? overview.value.status.pending : null,
  approved: overview.value ? overview.value.status.approved : null,
  rejected: overview.value ? overview.value.status.rejected : null,
  lowConfidence: overview.value ? overview.value.low_confidence : null,
  rate: overview.value ? overview.value.review_rate : null,
  total: overview.value ? overview.value.total : null
}))

/** 时序接口统一形状：{ keys, series:[{name,data}] } → { keys, values } */
function normaliseSeries(response) {
  if (!response || !Array.isArray(response.keys) || !Array.isArray(response.series) || !response.series.length) {
    return null
  }
  const values = Array.isArray(response.series[0].data) ? response.series[0].data : []
  return { keys: response.keys, values }
}

const hourlySeries = computed(() => normaliseSeries(hourly.value))
const weeklySeries = computed(() => normaliseSeries(weekly.value))

/** 今日违规类型占比（本系统台账即未戴头盔一类） */
const categoryPie = computed(() => {
  const total = todayTotal.value
  if (!total) return []
  return [{ value: total, name: '未佩戴头盔', itemStyle: { color: '#06b6d4' } }]
})

/** 今日高发卡口 TOP5（条宽按当日最大值归一） */
const topSpots = computed(() => {
  const items = Array.isArray(byCamera.value) ? byCamera.value : []
  const max = Math.max(1, ...items.map(item => item.total || 0))
  return items.slice(0, 5).map(item => ({
    id: item.camera_id,
    name: cameraName(item.camera_id),
    count: item.total,
    percent: Math.round(((item.total || 0) / max) * 100)
  }))
})

async function loadStats() {
  const [overviewRes, hourlyRes, weeklyRes, cameraRes] = await Promise.allSettled([
    fetchOverview(),
    fetchTimeseries({ bucket: 'hour', range: '24h' }),
    fetchTimeseries({ bucket: 'day', range: '7d' }),
    fetchByCamera('24h')
  ])

  if (overviewRes.status === 'fulfilled') { overview.value = overviewRes.value; overviewError.value = false }
  else { overview.value = null; overviewError.value = true }

  if (hourlyRes.status === 'fulfilled') { hourly.value = hourlyRes.value; hourlyError.value = false }
  else { hourly.value = null; hourlyError.value = true }

  if (weeklyRes.status === 'fulfilled') { weekly.value = weeklyRes.value; weeklyError.value = false }
  else { weekly.value = null; weeklyError.value = true }

  if (cameraRes.status === 'fulfilled') { byCamera.value = cameraRes.value?.items || []; byCameraError.value = false }
  else { byCamera.value = []; byCameraError.value = true }

  await Promise.allSettled([violationStore.fetchRecentRecords(12)])
}

/* ── 交互 ── */

function updateClock() {
  const d = new Date()
  currentTimeStr.value = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
}

function returnToAdmin() {
  router.push('/history')
}

function toggleFullScreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {})
    isFull.value = true
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(() => {})
      isFull.value = false
    }
  }
}

function openEvidence(record) {
  violationStore.openEvidenceModal(record)
}

function formatViolationType(text) {
  if (!text) return '违规行为'
  if (text.includes('未按规定佩戴安全头盔')) return '未按规定佩戴安全头盔'
  return text
}

async function pollEngineStatus() {
  try {
    const status = await getCameraStatus('CAM-03')
    const fps = Number(status?.fps)
    engineFps.value = Number.isFinite(fps) && fps > 0 ? fps.toFixed(1) : null
  } catch {
    engineFps.value = null
  }
}

/* ── 图表 ── */

function initCharts() {
  charts.forEach(c => c && c.dispose())
  charts = []

  // 1. 24小时逐时违规潮汐柱状图（stats.timeseries bucket=hour）
  if (hourlyChartRef.value && hourlySeries.value) {
    const c1 = echarts.init(hourlyChartRef.value)
    const { keys, values } = hourlySeries.value

    c1.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['未戴头盔'], textStyle: { color: '#94A3B8', fontSize: 11 }, top: 0, right: 0 },
      grid: { left: '3%', right: '3%', bottom: '5%', top: 25, containLabel: true },
      xAxis: {
        type: 'category',
        data: keys,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 11, interval: 2 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#1E293B', type: 'dashed' } },
        axisLabel: { color: '#64748B', fontSize: 11 }
      },
      series: [
        {
          name: '未戴头盔',
          type: 'bar',
          stack: 'total',
          data: values,
          itemStyle: { color: '#06b6d4' }
        }
      ]
    })
    charts.push(c1)
  }

  // 2. 未戴头盔线索发展趋势（stats.timeseries bucket=day, range=7d）
  if (trendChartRef.value && weeklySeries.value) {
    const c2 = echarts.init(trendChartRef.value)
    const { keys, values } = weeklySeries.value
    c2.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['未戴头盔'], textStyle: { color: '#94A3B8', fontSize: 11 }, top: 0, right: 0 },
      grid: { left: '3%', right: '4%', bottom: '5%', top: 25, containLabel: true },
      xAxis: {
        type: 'category',
        data: keys,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#1E293B', type: 'dashed' } },
        axisLabel: { color: '#64748B', fontSize: 11 }
      },
      series: [
        {
          name: '未戴头盔',
          type: 'line',
          smooth: true,
          data: values,
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2 }
        }
      ]
    })
    charts.push(c2)
  }

  // 3. 违规类型占比环形饼图（stats.overview）
  if (pieChartRef.value && categoryPie.value.length) {
    const c3 = echarts.init(pieChartRef.value)
    c3.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', formatter: '{b}: {c}起 ({d}%)' },
      legend: {
        orient: 'vertical',
        right: '2%',
        top: 'middle',
        textStyle: { color: '#94a3b8', fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10
      },
      series: [
        {
          name: '违规类型',
          type: 'pie',
          radius: ['45%', '72%'],
          center: ['38%', '50%'],
          avoidLabelOverlap: false,
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold', color: '#fff' } },
          data: categoryPie.value
        }
      ]
    })
    charts.push(c3)
  }
}

function handleResize() {
  charts.forEach(c => c && c.resize())
}

watch([hourlySeries, weeklySeries, categoryPie], async () => {
  await nextTick()
  initCharts()
})

onMounted(async () => {
  updateClock()
  timeTimer = setInterval(updateClock, 1000)
  statusTimer = setInterval(pollEngineStatus, 15000)
  pollEngineStatus()
  await loadStats()
  await nextTick()
  initCharts()
  // 大屏数据按 30s 轮询刷新；时序/概览仍走各接口，失败只影响对应卡片
  statsTimer = setInterval(loadStats, 30000)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (timeTimer) clearInterval(timeTimer)
  if (statusTimer) clearInterval(statusTimer)
  if (statsTimer) clearInterval(statsTimer)
  window.removeEventListener('resize', handleResize)
  charts.forEach(c => c && c.dispose())
})
</script>

<style scoped>
.style-scrollbar::-webkit-scrollbar {
  height: 4px;
}
.style-scrollbar::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.6);
  border-radius: 9999px;
}
.style-scrollbar::-webkit-scrollbar-thumb {
  background: #0891b2;
  border-radius: 9999px;
}
.style-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #06b6d4;
}
</style>
