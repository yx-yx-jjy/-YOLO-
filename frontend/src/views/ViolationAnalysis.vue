<template>
  <div class="space-y-4">
    <!-- 顶部状态栏与子页签 -->
    <div class="card flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">非机动车违规时空研判与风险预测</h2>
        <p class="text-[12px] font-normal mt-0.5" style="color: var(--c-ink-3);">多维度分析历史违规走势、卡口黑点分布及未来高危时段 AI 预警</p>
      </div>

      <!-- 子页签切换 -->
      <div class="flex items-center gap-0.5 p-0.5 rounded-md text-[13px]" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
        <button
          @click="activeTab = 'history'"
          class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5 transition"
          :style="activeTab === 'history'
            ? 'background-color: var(--c-surface); color: var(--c-primary); box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
            : 'color: var(--c-ink-2);'"
        >
          <el-icon :size="14"><Histogram /></el-icon>
          <span>时空分布研判</span>
        </button>
        <button
          @click="activeTab = 'forecast'"
          class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5 transition"
          :style="activeTab === 'forecast'
            ? 'background-color: var(--c-surface); color: var(--c-primary); box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
            : 'color: var(--c-ink-2);'"
        >
          <el-icon :size="14"><TrendCharts /></el-icon>
          <span>未来风险预测</span>
        </button>
      </div>
    </div>

    <MetricStrip :items="kpiItems" aria-label="研判数据概览" />

    <!-- ── 视图 1：时空数据研判（参考图 2 模式） ── -->
    <div v-show="activeTab === 'history'" class="space-y-4">
      <!-- 筛选栏 -->
      <div class="card flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3 text-[13px]">
          <div class="flex items-center gap-1.5">
            <span class="text-[12px]" style="color: var(--c-ink-3);">选择卡口:</span>
            <select 
              v-model="selectedSpot" 
              class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none"
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            >
              <option v-for="option in spotOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>

          <div class="flex items-center gap-1.5">
            <span class="text-[12px]" style="color: var(--c-ink-3);">时间范围:</span>
            <select 
              v-model="selectedTimeRange" 
              class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none"
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            >
              <option value="24h">近 24 小时</option>
              <option value="7d">近 7 天</option>
              <option value="30d">近 30 天</option>
            </select>
          </div>

          <button 
            @click="handleQueryAnalysis" 
            class="h-8 px-3.5 rounded-md text-[13px] font-normal text-white flex items-center gap-1.5 transition"
            style="background-color: var(--c-primary);"
            @mouseenter="$event.currentTarget.style.backgroundColor = '#4338CA'"
            @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
          >
            <el-icon :size="14"><Search /></el-icon>
            <span>查询研判</span>
          </button>
        </div>

        <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">
          已检索 {{ searchedCount }} 条违规线索台账
        </span>
      </div>

      <!-- 研判图表栏 (左：趋势面积折线图，右：路口 TOP 柱状图) -->
      <div class="grid grid-cols-12 gap-4">
        <!-- 左侧 8 列：违规时序与合规率趋势 -->
        <div class="col-span-8 card space-y-3">
          <div class="flex items-center justify-between pb-2" style="border-bottom: 1px solid var(--c-line);">
            <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">违规线索时段走势</h3>
            <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">未佩戴头盔线索</span>
          </div>
          <div v-if="analysisLoading" class="w-full h-72 flex items-center justify-center text-[13px]" style="color: var(--c-ink-3);">正在加载时序数据…</div>
          <div v-else-if="timeseriesError" class="w-full h-72 flex flex-col items-center justify-center gap-1 text-[13px]" style="color: var(--c-ink-3);">
            <span style="color: #B91C1C;">数据不可用</span>
            <span class="text-[12px]">时序接口请求失败，其余研判结果不受影响</span>
          </div>
          <div v-else ref="flowTrendChartRef" class="w-full h-72"></div>
        </div>

        <!-- 右侧 4 列：违规高发路口 TOP 排名 -->
        <div class="col-span-4 card space-y-3">
          <div class="flex items-center justify-between pb-2" style="border-bottom: 1px solid var(--c-line);">
            <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">高发卡口违规量 TOP 排名</h3>
            <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">抓拍频次</span>
          </div>
          <div v-if="analysisLoading" class="w-full h-72 flex items-center justify-center text-[13px]" style="color: var(--c-ink-3);">正在加载卡口聚合…</div>
          <div v-else-if="byCameraError" class="w-full h-72 flex items-center justify-center text-[13px]" style="color: var(--c-ink-3);">数据不可用</div>
          <div v-else ref="topSpotsChartRef" class="w-full h-72"></div>
        </div>
      </div>

      <!-- 底部数据明细表格 -->
      <div class="card !p-0 overflow-hidden">
        <div class="p-4 flex items-center justify-between" style="border-bottom: 1px solid var(--c-line);">
          <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">卡口违规研判明细台账</h3>
          <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">共 {{ intersectionTable.length }} 个核心路段监测点位</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-[13px] table-fixed" style="color: var(--c-ink);">
            <colgroup>
              <col style="width: 70px;" />
              <col style="width: 220px;" />
              <col style="width: 140px;" />
              <col style="width: 130px;" />
              <col style="width: 130px;" />
              <col style="width: 130px;" />
              <col style="width: 160px;" />
            </colgroup>
            <thead>
              <tr style="background-color: var(--c-page); border-bottom: 1px solid var(--c-line);">
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">序号</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">卡口</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">违规线索数</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">未佩戴头盔</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">平均置信度</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-center" style="color: #64748B;">统计截止时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="analysisLoading">
                <td colspan="6" class="h-16 text-center text-[13px]" style="color: var(--c-ink-3);">正在加载卡口研判数据…</td>
              </tr>
              <tr v-else-if="byCameraError">
                <td colspan="6" class="h-16 text-center text-[13px]" style="color: #B91C1C;">
                  数据加载失败：{{ analysisErrorText }}
                  <button class="ml-2 underline" style="color: var(--c-primary);" @click="handleQueryAnalysis">重试</button>
                </td>
              </tr>
              <tr v-else-if="intersectionTable.length === 0">
                <td colspan="6" class="h-16 text-center text-[13px]" style="color: var(--c-ink-3);">当前筛选范围内暂无卡口违规数据</td>
              </tr>
              <tr 
                v-for="(row, idx) in intersectionTable" 
                :key="row.name"
                class="h-12 align-middle"
                style="border-bottom: 1px solid var(--c-line);"
                @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'"
                @mouseleave="$event.currentTarget.style.backgroundColor = ''"
              >
                <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink-3);">{{ idx + 1 }}</td>
                <td class="h-12 px-3 font-medium whitespace-nowrap" style="color: var(--c-ink);">{{ row.name }}</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-right" style="color: var(--c-ink);">{{ row.total }}</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-right" style="color: #B45309;">{{ row.noHelmet }}</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-right" :style="{ color: confidenceColor(row.avgConfidence) }">{{ row.avgConfidence }}%</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-center text-[12px]" style="color: var(--c-ink-3);">{{ row.time }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── 视图 2：未来风险预测（参考图 3 模式） ── -->
    <div v-show="activeTab === 'forecast'" class="space-y-4">
      <!-- 预测操作区 -->
      <div class="card flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3 text-[13px]">
          <div class="flex items-center gap-1.5">
            <span class="text-[12px]" style="color: var(--c-ink-3);">目标预测卡口:</span>
            <select 
              v-model="forecastSpot" 
              class="h-8 px-3 rounded-md text-[13px] font-normal focus:outline-none"
              style="background-color: var(--c-surface); border: 1px solid var(--c-line); color: var(--c-ink);"
            >
              <option v-for="cam in CAMERAS" :key="cam.id" :value="cam.id">
                {{ cam.name }}（{{ cam.area }}）
              </option>
            </select>
          </div>

          <button 
            @click="handleRunForecast" 
            class="h-8 px-3.5 rounded-md text-[13px] font-normal text-white flex items-center gap-1.5 transition"
            style="background-color: var(--c-primary);"
            @mouseenter="$event.currentTarget.style.backgroundColor = '#4338CA'"
            @mouseleave="$event.currentTarget.style.backgroundColor = 'var(--c-primary)'"
          >
            <el-icon :size="14"><VideoPlay /></el-icon>
            <span>开始时序推演预测</span>
          </button>
        </div>

        <span class="flex items-center gap-2 text-[12px]" style="color: var(--c-ink-3);">
          <span>推演口径: 近 7 天同时段抓拍均值外推，预测未来 3 小时走势</span>
          <DemoBadge hint="当前未接入时序预测模型，此处为基于历史台账的朴素外推，仅供演示，不可用于警力调度决策" />
        </span>
      </div>

      <!-- 预测图表两栏 (实线历史 + 虚线预测) -->
      <div class="grid grid-cols-2 gap-4">
        <!-- 图表 1：车流量与违规走势 (历史 + 预测) -->
        <div class="card space-y-3">
          <div class="flex items-center justify-between pb-2" style="border-bottom: 1px solid var(--c-line);">
            <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">违规骑行态势 (历史已捕获 + 未来预测)</h3>
            <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">实线: 已记录 / 虚线: 预测区间</span>
          </div>
          <div v-if="forecastLoading" class="w-full h-72 flex items-center justify-center text-[13px]" style="color: var(--c-ink-3);">正在加载推演数据…</div>
          <div v-else-if="forecastError" class="w-full h-72 flex items-center justify-center text-[13px]" style="color: var(--c-ink-3);">数据不可用</div>
          <div v-else ref="forecastLineChartRef" class="w-full h-72"></div>
        </div>

        <!-- 图表 2：违规风险指数预测 (历史 + 预测) -->
        <div class="card space-y-3">
          <div class="flex items-center justify-between pb-2" style="border-bottom: 1px solid var(--c-line);">
            <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">卡口综合风险等级指数 (历史 + 预测)</h3>
            <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">指数范围: 0.0 ~ 2.0</span>
          </div>
          <div v-if="forecastLoading" class="w-full h-72 flex items-center justify-center text-[13px]" style="color: var(--c-ink-3);">正在加载推演数据…</div>
          <div v-else-if="forecastError" class="w-full h-72 flex items-center justify-center text-[13px]" style="color: var(--c-ink-3);">数据不可用</div>
          <div v-else ref="riskIndexChartRef" class="w-full h-72"></div>
        </div>
      </div>

      <!-- 预测结果明细台账 -->
      <div class="card !p-0 overflow-hidden">
        <div class="p-4 flex items-center justify-between" style="border-bottom: 1px solid var(--c-line);">
          <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">未来时段卡口风险研判结果清单</h3>
          <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">未来 3 小时滚动窗口</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-[13px] table-fixed" style="color: var(--c-ink);">
            <colgroup>
              <col style="width: 70px;" />
              <col style="width: 150px;" />
              <col style="width: 220px;" />
              <col style="width: 140px;" />
              <col style="width: 140px;" />
              <col style="width: 280px;" />
            </colgroup>
            <thead>
              <tr style="background-color: var(--c-page); border-bottom: 1px solid var(--c-line);">
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">序号</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">推演时段</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">预测卡口</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-right" style="color: #64748B;">预测违规线索</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap text-center" style="color: #64748B;">风险预警等级</th>
                <th class="h-12 px-3 text-[12px] font-normal whitespace-nowrap" style="color: #64748B;">交管建议预处置策略</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="forecastLoading">
                <td colspan="6" class="h-16 text-center text-[13px]" style="color: var(--c-ink-3);">正在加载推演结果…</td>
              </tr>
              <tr v-else-if="forecastError">
                <td colspan="6" class="h-16 text-center text-[13px]" style="color: #B91C1C;">
                  数据加载失败：请稍后重试
                  <button class="ml-2 underline" style="color: var(--c-primary);" @click="handleRunForecast">重试</button>
                </td>
              </tr>
              <tr v-else-if="forecastTable.length === 0">
                <td colspan="6" class="h-16 text-center text-[13px]" style="color: var(--c-ink-3);">暂无可用的推演结果</td>
              </tr>
              <tr 
                v-for="(row, idx) in forecastTable" 
                :key="row.time"
                class="h-12 align-middle"
                style="border-bottom: 1px solid var(--c-line);"
                @mouseenter="$event.currentTarget.style.backgroundColor = 'var(--c-page)'"
                @mouseleave="$event.currentTarget.style.backgroundColor = ''"
              >
                <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink-3);">{{ idx + 1 }}</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap" style="color: var(--c-ink-2);">{{ row.time }}</td>
                <td class="h-12 px-3 font-medium whitespace-nowrap" style="color: var(--c-ink);">{{ row.spot }}</td>
                <td class="h-12 px-3 font-mono whitespace-nowrap text-right" style="color: #B45309;">{{ row.count }} 起</td>
                <td class="h-12 px-3 whitespace-nowrap text-center">
                  <span 
                    class="px-2 py-0.5 rounded text-[12px] font-normal whitespace-nowrap"
                    :style="row.level === '高危预警'
                      ? 'background-color: #FEF2F2; color: #B91C1C;'
                      : row.level === '中度风险'
                      ? 'background-color: #FFFBEB; color: #B45309;'
                      : 'background-color: #F0FDF4; color: #15803D;'"
                  >
                    {{ row.level }}
                  </span>
                </td>
                <td class="h-12 px-3 whitespace-nowrap truncate text-[12px]" :title="row.action" style="color: var(--c-ink-2);">
                  {{ row.action }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import MetricStrip from '../components/MetricStrip.vue'
import DemoBadge from '../components/DemoBadge.vue'
import { CAMERAS, cameraKey, cameraName } from '../data/cameras'
import { fetchTimeseries, fetchByCamera, fetchForecast } from '../services/statsApi'
import { getApiErrorMessage } from '../services/http'

const activeTab = ref('history')

// 表单侧（草稿）与结果侧（已应用）分开：改完筛选要按「查询研判」才生效，
// 这样按钮点下去是真的在重算，而不是只弹一句提示。
const selectedSpot = ref('ALL')
const selectedTimeRange = ref('24h')
const forecastSpot = ref('CAM-03')

const appliedSpot = ref('ALL')
const appliedTimeRange = ref('24h')
const appliedForecastSpot = ref('CAM-03')

const flowTrendChartRef = ref(null)
const topSpotsChartRef = ref(null)
const forecastLineChartRef = ref(null)
const riskIndexChartRef = ref(null)

let charts = []

/* ── 研判数据全部走后端聚合接口：timeseries + by-camera + forecast ──
   服务端分页后 records 只是台账某一页，不能再拿它当"全量台账"来聚合。 */
const analysisLoading = ref(false)
const analysisError = ref(null)
const timeseriesData = ref(null)
const timeseriesError = ref(false)
const byCameraItems = ref([])
const byCameraError = ref(false)

const forecastLoading = ref(false)
const forecastData = ref(null)
const forecastError = ref(false)

const spotOptions = computed(() => [
  { value: 'ALL', label: '全部卡口' },
  ...CAMERAS.map(cam => ({ value: cam.id, label: `${cam.name}（${cam.area}）` }))
])

/** avg_confidence 口径未在契约中锁定，兼容 0~1 与 0~100 两种 */
function toPercent(raw) {
  if (raw === null || raw === undefined || Number.isNaN(Number(raw))) return 0
  const n = Number(raw)
  return n <= 1 ? Math.round(n * 100) : Math.round(n)
}

/** 按选定路口收窄（by-camera 聚合结果） */
const scopedByCamera = computed(() => {
  const items = byCameraItems.value || []
  if (appliedSpot.value === 'ALL') return items
  return items.filter(item => cameraKey(item.camera_id) === appliedSpot.value)
})

/**
 * 卡口研判明细：由 /api/stats/by-camera 按点位聚合结果映射。
 * 原来这 6 行写死了"过车总量 1,420 辆 / 头盔合规率 87.3%"——
 * 台账里根本没有"过车总量"这个数据源，与其编一个数，不如换成真算得出来的列。
 */
const intersectionTable = computed(() => (
  scopedByCamera.value
    .map(item => {
      const id = cameraKey(item.camera_id)
      return {
        id,
        name: `${id}: ${item.name || cameraName(id)}`,
        total: item.total ?? 0,
        noHelmet: item.no_helmet ?? item.total ?? 0,
        avgConfidence: toPercent(item.avg_confidence),
        time: item.last_capture_time || '—'
      }
    })
    .sort((a, b) => b.total - a.total)
))

/** 顶部概览条：由上方研判结果汇总；接口失败时显示「—」 */
const kpiItems = computed(() => {
  if (byCameraError.value) {
    return [
      { label: '违规线索总数', value: '—', unit: '起' },
      { label: '未佩戴头盔', value: '—', unit: '起', tone: 'warning' },
      { label: '覆盖卡口', value: '—', unit: '处' },
      { label: '平均置信度', value: '—', unit: '%', tone: 'default' }
    ]
  }
  const rows = intersectionTable.value
  const total = rows.reduce((sum, row) => sum + row.total, 0)
  const avg = total
    ? Math.round(rows.reduce((sum, row) => sum + row.avgConfidence * row.total, 0) / total)
    : 0

  return [
    { label: '违规线索总数', value: total, unit: '起' },
    { label: '未佩戴头盔', value: rows.reduce((sum, row) => sum + row.noHelmet, 0), unit: '起', tone: 'warning' },
    { label: '覆盖卡口', value: rows.length, unit: '处' },
    { label: '平均置信度', value: avg, unit: '%', tone: avg >= 85 ? 'success' : 'warning' }
  ]
})

const searchedCount = computed(() => (
  intersectionTable.value.reduce((sum, row) => sum + row.total, 0)
))

const analysisErrorText = computed(() => getApiErrorMessage(analysisError.value))

/** 走势图：取自 /api/stats/timeseries 的 keys + 单条 series */
const flowSeries = computed(() => {
  const data = timeseriesData.value
  if (!data || !Array.isArray(data.keys)) return { keys: [], helmet: [] }
  const first = Array.isArray(data.series) && data.series.length ? data.series[0] : null
  return {
    keys: data.keys,
    helmet: first && Array.isArray(first.data) ? first.data : []
  }
})

/** 高发路口横向柱状图（ECharts 的类目轴自下而上，故此处反转） */
const topSpotsSeries = computed(() => {
  const rows = [...(byCameraItems.value || [])]
    .sort((a, b) => (b.total || 0) - (a.total || 0))
    .slice(0, 6)
  return {
    names: rows.map(row => row.name || cameraName(cameraKey(row.camera_id))).reverse(),
    values: rows.map(row => row.total || 0).reverse()
  }
})

/**
 * 预测视图的数据口径由后端 /api/stats/forecast 统一给出：
 *   历史段 = 所选路口当日最近 5 小时真实抓拍；预测段 = 近 7 天同时刻均值外推。
 * 仍是朴素外推（架构稿 R4 口径待确认），界面明确标注演示口径，不冒充 AI 模型。
 */
const forecastSeries = computed(() => {
  const data = forecastData.value || {}
  const history = data.history || {}
  const forecast = data.forecast || {}
  return {
    historyHours: Array.isArray(history.keys) ? history.keys : [],
    historyValues: Array.isArray(history.values) ? history.values : [],
    forecastHours: Array.isArray(forecast.keys) ? forecast.keys : [],
    forecastValues: Array.isArray(forecast.values) ? forecast.values : []
  }
})

/** 风险指数 = 预测线索数线性归一到 0~2，只用于表达相对高低，不代表模型输出 */
function riskIndexOf(value) {
  return Number(Math.min(2, value / 10).toFixed(2))
}

// 置信度分档上色：口径统一在 utils/confidence.js（唯一事实来源）。
// 本页拿到的是百分数，这里换算成 0~1 再交给统一样板。
import { confidenceColor as confidenceColorShared } from '../utils/confidence'
function confidenceColor(percent) {
  if (percent == null) return 'var(--c-ink-3)'
  return confidenceColorShared(Number(percent) / 100)
}

const forecastTable = computed(() => {
  const { forecastHours, forecastValues } = forecastSeries.value
  const spot = cameraName(appliedForecastSpot.value)
  return forecastHours.map((hour, index) => {
    const count = forecastValues[index]
    const level = count >= 12 ? '高危预警' : count >= 6 ? '中度风险' : '常态平稳'
    const action = level === '高危预警'
      ? '建议通知执勤交警在路口引导，前置安全喊话'
      : level === '中度风险'
        ? '骑行潮启动，开启连续多帧去抖跟踪'
        : '前端探头自动抓拍，无需增派巡逻'
    return { time: hour, spot, count, level, action }
  })
})

/** 拉取研判数据：时序走势 + 卡口聚合，各自独立失败互不牵连 */
async function loadAnalysis() {
  analysisLoading.value = true
  analysisError.value = null
  const [tsRes, camRes] = await Promise.allSettled([
    fetchTimeseries({
      bucket: appliedTimeRange.value === '24h' ? 'hour' : 'day',
      range: appliedTimeRange.value,
      camera_id: appliedSpot.value
    }),
    fetchByCamera(appliedTimeRange.value)
  ])

  if (tsRes.status === 'fulfilled') { timeseriesData.value = tsRes.value; timeseriesError.value = false }
  else { timeseriesData.value = null; timeseriesError.value = true }

  if (camRes.status === 'fulfilled') {
    byCameraItems.value = camRes.value?.items || []
    byCameraError.value = false
  } else {
    byCameraItems.value = []
    byCameraError.value = true
  }

  analysisError.value = camRes.status === 'rejected' ? camRes.reason : null
  analysisLoading.value = false
}

async function loadForecast() {
  forecastLoading.value = true
  try {
    forecastData.value = await fetchForecast(appliedForecastSpot.value)
    forecastError.value = false
  } catch (error) {
    forecastData.value = null
    forecastError.value = true
  } finally {
    forecastLoading.value = false
  }
}

async function handleQueryAnalysis() {
  appliedSpot.value = selectedSpot.value
  appliedTimeRange.value = selectedTimeRange.value
  await loadAnalysis()
  await nextTick()
  initCharts()
  if (analysisError.value) {
    ElMessage.error(`研判数据加载失败：${analysisErrorText.value}`)
    return
  }
  const rows = intersectionTable.value
  const total = rows.reduce((sum, row) => sum + row.total, 0)
  ElMessage.success(`已按当前条件重新汇总：覆盖 ${rows.length} 个点位、${total} 条违规线索`)
}

async function handleRunForecast() {
  appliedForecastSpot.value = forecastSpot.value
  await loadForecast()
  await nextTick()
  initCharts()
  if (forecastError.value) {
    ElMessage.error('时序推演数据加载失败，请稍后重试')
    return
  }
  const peak = Math.max(0, ...forecastSeries.value.forecastValues)
  ElMessage.success(
    `已按近 7 天同时段均值完成【${cameraName(appliedForecastSpot.value)}】未来 3 小时推演，峰值 ${peak} 起`
  )
}

function initCharts() {
  charts.forEach(c => c && c.dispose())
  charts = []

  const chartPrimary = '#1D4ED8'
  const chartGray = '#94A3B8'
  const chartWarning = '#B45309'
  const chartGreen = '#15803D'

  // 1. 违规走势图 (历史研判)：由当前筛选范围内的台账分桶得出，不再写死
  if (flowTrendChartRef.value && activeTab.value === 'history') {
    const c1 = echarts.init(flowTrendChartRef.value)
    const { keys, helmet } = flowSeries.value
    c1.setOption({
      backgroundColor: '#ffffff',
      tooltip: { trigger: 'axis' },
      legend: { data: ['未佩戴头盔 (起)'], top: 0, textStyle: { fontSize: 12, color: '#475569' } },
      grid: { left: '3%', right: '3%', bottom: '5%', top: 35, containLabel: true },
      xAxis: { type: 'category', data: keys, axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748B' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } },
      series: [
        {
          name: '未佩戴头盔 (起)',
          type: 'line',
          smooth: true,
          data: helmet,
          itemStyle: { color: chartWarning },
          lineStyle: { width: 2, color: chartWarning },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(180, 83, 9, 0.16)' },
              { offset: 1, color: 'rgba(180, 83, 9, 0.0)' }
            ])
          }
        }
      ]
    })
    charts.push(c1)
  }

  // 2. 高发路口 TOP 柱状图 (横向)：由研判台账按点位排序派生
  if (topSpotsChartRef.value && activeTab.value === 'history') {
    const c2 = echarts.init(topSpotsChartRef.value)
    const { names, values } = topSpotsSeries.value
    c2.setOption({
      backgroundColor: '#ffffff',
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '8%', bottom: '5%', top: 15, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } },
      yAxis: {
        type: 'category',
        data: names,
        axisLine: { lineStyle: { color: '#E2E8F0' } },
        axisLabel: { color: '#475569', fontSize: 11 }
      },
      series: [
        {
          name: '违规线索数',
          type: 'bar',
          data: values,
          barWidth: 16,
          itemStyle: {
            color: chartPrimary,
            borderRadius: [0, 4, 4, 0]
          },
          label: { show: true, position: 'right', color: '#475569', fontSize: 11 }
        }
      ]
    })
    charts.push(c2)
  }

  // 3. 预测折线图 (实线历史 + 虚线预测)
  //    历史段 = 当日真实抓拍；预测段 = 近 7 天同时段均值外推（演示口径）
  if (forecastLineChartRef.value && activeTab.value === 'forecast') {
    const c3 = echarts.init(forecastLineChartRef.value)
    const { historyHours, historyValues, forecastHours, forecastValues } = forecastSeries.value
    const times = [...historyHours, ...forecastHours]
    const historyData = [...historyValues, ...forecastHours.map(() => null)]
    // 预测线从最后一个历史点接力，视觉上才连得上
    const forecastData = [
      ...historyHours.map((_, index) => (index === historyHours.length - 1 ? historyValues[index] : null)),
      ...forecastValues
    ]

    c3.setOption({
      backgroundColor: '#ffffff',
      tooltip: { trigger: 'axis' },
      legend: { data: ['历史违规 (起)', '预测违规 (起)'], top: 0, textStyle: { fontSize: 12, color: '#475569' } },
      grid: { left: '3%', right: '3%', bottom: '5%', top: 35, containLabel: true },
      xAxis: { type: 'category', data: times, axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748B' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } },
      series: [
        {
          name: '历史违规 (起)',
          type: 'line',
          smooth: true,
          data: historyData,
          itemStyle: { color: chartPrimary },
          lineStyle: { width: 2.5, color: chartPrimary }
        },
        {
          name: '预测违规 (起)',
          type: 'line',
          smooth: true,
          data: forecastData,
          itemStyle: { color: '#B91C1C' },
          lineStyle: { width: 2.5, type: 'dashed', color: '#B91C1C' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(185, 28, 28, 0.16)' },
              { offset: 1, color: 'rgba(185, 28, 28, 0.0)' }
            ])
          }
        }
      ]
    })
    charts.push(c3)
  }

  // 4. 风险指数预测 (实线历史 + 虚线预测)
  if (riskIndexChartRef.value && activeTab.value === 'forecast') {
    const c4 = echarts.init(riskIndexChartRef.value)
    const { historyHours, historyValues, forecastHours, forecastValues } = forecastSeries.value
    const times = [...historyHours, ...forecastHours]
    const histRisk = [...historyValues.map(riskIndexOf), ...forecastHours.map(() => null)]
    const foreRisk = [
      ...historyHours.map((_, index) => (index === historyHours.length - 1 ? riskIndexOf(historyValues[index]) : null)),
      ...forecastValues.map(riskIndexOf)
    ]

    c4.setOption({
      backgroundColor: '#ffffff',
      tooltip: { trigger: 'axis' },
      legend: { data: ['历史风险指数', '推演风险指数'], top: 0, textStyle: { fontSize: 12, color: '#475569' } },
      grid: { left: '3%', right: '3%', bottom: '5%', top: 35, containLabel: true },
      xAxis: { type: 'category', data: times, axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748B' } },
      yAxis: { type: 'value', min: 0, max: 2.0, splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } },
      series: [
        {
          name: '历史风险指数',
          type: 'line',
          smooth: true,
          data: histRisk,
          itemStyle: { color: chartGreen },
          lineStyle: { width: 2, color: chartGreen }
        },
        {
          name: '推演风险指数',
          type: 'line',
          smooth: true,
          data: foreRisk,
          itemStyle: { color: chartWarning },
          lineStyle: { width: 2, type: 'dashed', color: chartWarning }
        }
      ]
    })
    charts.push(c4)
  }
}

// 切换页签、或筛选结果发生变化时重绘图表
watch([activeTab, flowSeries, topSpotsSeries, forecastSeries], async () => {
  await nextTick()
  initCharts()
})

onMounted(async () => {
  await Promise.allSettled([loadAnalysis(), loadForecast()])
  await nextTick()
  initCharts()
  window.addEventListener('resize', handleResize)
})

function handleResize() {
  charts.forEach(c => c && c.resize())
}

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  charts.forEach(c => c && c.dispose())
})
</script>
