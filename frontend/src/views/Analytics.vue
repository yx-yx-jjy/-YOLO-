<template>
  <div class="space-y-5">
    <!-- 顶部标题栏 -->
    <div class="glass-panel p-4 rounded-xl border border-slate-800 flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold text-white">智慧交管 - 全域非机动车安全大数据全景看板</h2>
        <p class="text-xs text-slate-400 mt-0.5">违规时段分布 · 置信度构成 · 各卡口断面统计</p>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-400">统计口径:</span>
        <span class="px-2.5 py-1 rounded bg-slate-800 text-slate-300 text-xs">近 24 小时</span>
      </div>
    </div>

    <!-- 3 个可视化图表卡片：全部来自后端统计接口 -->
    <div class="grid grid-cols-2 gap-5">
      <!-- 图表 1: 24小时违规高发时段波动趋势 (折线面积图) -->
      <div class="glass-panel p-5 rounded-xl border border-slate-800 space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-bold text-white flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
            24小时违规高发时段分布
          </span>
          <span class="text-xs text-slate-400 font-mono">来自 /api/stats/timeseries</span>
        </div>
        <div class="relative">
          <div ref="hourlyChartRef" class="w-full h-72" v-show="!hourlyError"></div>
          <div v-if="hourlyError" class="absolute inset-0 flex items-center justify-center text-xs" style="color: #64748B;">数据不可用</div>
        </div>
      </div>

      <!-- 图表 2: 违规记录置信度分布 (环形饼图) -->
      <div class="glass-panel p-5 rounded-xl border border-slate-800 space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-bold text-white flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
            违规记录置信度分布
          </span>
          <span class="text-xs text-slate-400 font-mono">来自 /api/stats/overview</span>
        </div>
        <div class="relative">
          <div ref="pieChartRef" class="w-full h-72" v-show="!overviewError"></div>
          <div v-if="overviewError" class="absolute inset-0 flex items-center justify-center text-xs" style="color: #64748B;">数据不可用</div>
        </div>
      </div>

      <!-- 图表 3: 各卡口违规分布 (柱状图) -->
      <div class="glass-panel p-5 rounded-xl border border-slate-800 space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-bold text-white flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
            各卡口违规记录分布
          </span>
          <span class="text-xs text-slate-400 font-mono">来自 /api/stats/by-camera</span>
        </div>
        <div class="relative">
          <div ref="barChartRef" class="w-full h-72" v-show="!byCameraError"></div>
          <div v-if="byCameraError" class="absolute inset-0 flex items-center justify-center text-xs" style="color: #64748B;">数据不可用</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 本页所有数字都来自后端统计接口，不再内置任何演示数值。
 * 单个接口失败只让对应卡片显示「数据不可用」，其余卡片照常渲染
 * （与 ScreenDashboard.vue 同一套处理方式）。
 */
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { fetchOverview, fetchTimeseries, fetchByCamera } from '../services/statsApi'

const hourlyChartRef = ref(null)
const pieChartRef = ref(null)
const barChartRef = ref(null)

let charts = []

const overview = ref(null)
const overviewError = ref(false)
const hourly = ref(null)
const hourlyError = ref(false)
const byCamera = ref(null)
const byCameraError = ref(false)

/** 接口没回来时显示「—」，不用 0 或示例值假装有数据 */
function stat(value) {
  return value === null || value === undefined ? '—' : value
}

/** 饼图只有一段数据时 ECharts 会画成整圆，补一个占位段避免误读成 100% */
function withPlaceholder(items) {
  const total = items.reduce((sum, item) => sum + item.value, 0)
  if (total > 0) return items
  return [...items, { value: 1, name: '暂无数据', itemStyle: { color: '#1e293b' } }]
}

function initCharts() {
  charts.forEach(c => c && c.dispose())
  charts = []

  // 1. 24 小时分布折线图：/api/stats/timeseries?bucket=hour
  if (hourlyChartRef.value && hourly.value) {
    const c1 = echarts.init(hourlyChartRef.value)
    c1.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: '#94a3b8' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: hourly.value.keys || [],
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#334155' } },
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' }
      },
      series: (hourly.value.series || []).map(s => ({
        name: s.name,
        type: 'line',
        smooth: true,
        data: s.data || [],
        itemStyle: { color: '#f43f5e' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(244,63,94,0.4)' },
            { offset: 1, color: 'rgba(244,63,94,0.0)' }
          ])
        }
      }))
    })
    charts.push(c1)
  }

  // 2. 置信度分布环形图：低置信度 / 其余，来自 /api/stats/overview
  if (pieChartRef.value && overview.value) {
    const total = overview.value.total ?? 0
    const lowConf = overview.value.low_confidence ?? 0
    const c2 = echarts.init(pieChartRef.value)
    c2.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: { bottom: '0%', textStyle: { color: '#94a3b8' } },
      series: [
        {
          name: '置信度分布',
          type: 'pie',
          radius: ['45%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 8, borderColor: '#0f172a', borderWidth: 2 },
          label: { show: false },
          data: withPlaceholder([
            { value: Math.max(total - lowConf, 0), name: `常规置信度（${stat(total - lowConf)} 条）`, itemStyle: { color: '#f43f5e' } },
            { value: lowConf, name: `低置信度待复核（${stat(lowConf)} 条）`, itemStyle: { color: '#a855f7' } }
          ])
        }
      ]
    })
    charts.push(c2)
  }

  // 3. 各卡口违规记录数：/api/stats/by-camera
  if (barChartRef.value && byCamera.value) {
    const items = (byCamera.value || []).slice(0, 8)
    const c3 = echarts.init(barChartRef.value)
    c3.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: items.map(item => item.name || item.camera_id),
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', interval: 0, fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } }
      },
      series: [
        {
          name: '违规记录数',
          type: 'bar',
          data: items.map(item => item.total ?? 0),
          barWidth: 26,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#10b981' },
              { offset: 1, color: '#047857' }
            ])
          }
        }
      ]
    })
    charts.push(c3)
  }
}

onMounted(async () => {
  // 三个接口互不依赖，并发拉取；单个失败只影响对应卡片
  const [overviewRes, hourlyRes, cameraRes] = await Promise.allSettled([
    fetchOverview(),
    fetchTimeseries({ bucket: 'hour', range: '24h' }),
    fetchByCamera('24h')
  ])

  if (overviewRes.status === 'fulfilled') { overview.value = overviewRes.value; overviewError.value = false }
  else { overview.value = null; overviewError.value = true }

  if (hourlyRes.status === 'fulfilled') { hourly.value = hourlyRes.value; hourlyError.value = false }
  else { hourly.value = null; hourlyError.value = true }

  if (cameraRes.status === 'fulfilled') { byCamera.value = cameraRes.value?.items || []; byCameraError.value = false }
  else { byCamera.value = []; byCameraError.value = true }

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
