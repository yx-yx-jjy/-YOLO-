<template>
  <div class="space-y-4">
    <!-- 顶部状态栏 -->
    <div class="card flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <div>
          <h2 class="text-[16px] font-medium" style="color: var(--c-ink);">指标展示</h2>
          <p class="text-[12px] font-normal mt-0.5" style="color: var(--c-ink-3);">训练指标快照 · 未实时读取训练产物</p>
        </div>
        <DemoBadge hint="数值取自训练产物 results.csv 与训练日志（yolo11s-helmet-voc-v5-continue），为历史实测快照，尚未与后端自动同步；请勿直接用于验收结论" />
      </div>

      <!-- 子页签 -->
      <div class="flex items-center gap-0.5 p-0.5 rounded-md text-[13px]" style="background-color: var(--c-page); border: 1px solid var(--c-line);">
        <button
          @click="activeTab = 'summary'"
          class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5"
          :style="activeTab === 'summary'
            ? 'background-color: var(--c-surface); color: var(--c-primary); box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
            : 'color: var(--c-ink-2);'"
        >
          <el-icon :size="14"><DataLine /></el-icon>
          <span>指标汇总</span>
        </button>
        <button
          @click="activeTab = 'curves'"
          class="px-3 py-1 rounded-md font-normal whitespace-nowrap flex items-center gap-1.5"
          :style="activeTab === 'curves'
            ? 'background-color: var(--c-surface); color: var(--c-primary); box-shadow: 0 1px 2px rgba(15,23,42,0.04);'
            : 'color: var(--c-ink-2);'"
        >
          <el-icon :size="14"><TrendCharts /></el-icon>
          <span>训练曲线 (Loss/LR)</span>
        </button>
      </div>
    </div>

    <!-- 视图 1：指标汇总 -->
    <div v-show="activeTab === 'summary'" class="space-y-4">
      <!-- 4 个指标卡片 -->
      <div class="grid grid-cols-4 gap-4">
        <div v-for="item in metricCards" :key="item.label" class="card">
          <div class="text-[12px] font-normal mb-1" style="color: var(--c-ink-3);">{{ item.subtitle }}</div>
          <div class="text-[16px] font-medium font-mono" style="color: var(--c-primary);">
            {{ item.value }}
          </div>
          <div class="text-[12px] font-normal mt-2 flex items-center justify-between">
            <span class="px-2 py-0.5 rounded text-[12px]" style="background-color: var(--c-primary-weak); color: var(--c-primary);">{{ item.label }}</span>
            <span class="font-mono" style="color: var(--c-ink-3);">{{ item.note }}</span>
          </div>
        </div>
      </div>

      <!-- 训练收敛指标柱状图 -->
      <div class="card">
        <div class="flex items-center justify-between pb-3 mb-3" style="border-bottom: 1px solid var(--c-line);">
          <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">训练收敛指标（最佳轮次 Epoch 9）</h3>
          <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">四项核心目标检测量化指标</span>
        </div>
        <div ref="barSummaryRef" class="w-full h-[336px]"></div>
      </div>

      <!-- 学习率衰减曲线 -->
      <div class="card">
        <div class="flex items-center justify-between pb-3 mb-3" style="border-bottom: 1px solid var(--c-line);">
          <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">学习率衰减曲线 (Learning Rate Schedule)</h3>
          <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">线性衰减（cos_lr=False，warmup 3 轮）</span>
        </div>
        <div ref="lrCurveRef" class="w-full h-[272px]"></div>
      </div>
    </div>

    <!-- 视图 2：训练曲线 -->
    <div v-show="activeTab === 'curves'" class="space-y-4">
      <div class="grid grid-cols-1 gap-4">
        <!-- Loss 曲线 -->
        <div class="card">
          <div class="flex items-center justify-between pb-3 mb-3" style="border-bottom: 1px solid var(--c-line);">
            <h3 class="text-[14px] font-medium" style="color: var(--c-ink);">损失函数收敛曲线 (Loss)</h3>
            <span class="text-[12px] font-mono" style="color: var(--c-ink-3);">Box Loss & Cls Loss</span>
          </div>
          <div ref="lossCurveRef" class="w-full h-[336px]"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import DemoBadge from '../components/DemoBadge.vue'

const activeTab = ref('summary')
const barSummaryRef = ref(null)
const lrCurveRef = ref(null)
const lossCurveRef = ref(null)

let charts = []

/**
 * 以下数值全部来自训练产物，未做任何估算或外推：
 *   - mAP / Precision / Recall：backend/runs/violation/yolo11s-helmet-voc-v5-continue/results.csv 第 9 行（最佳轮次）
 *   - Loss / LR：同文件 1~10 轮逐轮记录
 *   - 参数量：训练日志 "YOLO11s summary: 181 layers, 9,428,566 parameters"（真实）
 *   - ⚠️ GFLOPs：日志同行打印的 "21.5 GFLOPs" 是默认 imgsz=640 口径；960 输入下实测为 48.48 G，两者勿混用
 * 网络结构为官方 YOLO11s 原版，未做任何改动，因此不存在消融实验数据，本页不展示消融对比。
 */
const BEST_EPOCH = 9

const metricCards = [
  { subtitle: `最佳轮次实测 (Epoch ${BEST_EPOCH})`, value: '0.786', label: 'mAP@50', note: 'IoU 0.50' },
  { subtitle: '综合定位精度', value: '0.525', label: 'mAP@50-95', note: 'IoU 0.50:0.95' },
  { subtitle: '查准率 (Precision)', value: '0.803', label: 'Precision', note: `Epoch ${BEST_EPOCH}` },
  { subtitle: '召回率 (Recall)', value: '0.677', label: 'Recall', note: `Epoch ${BEST_EPOCH}` }
]

// 逐轮实测训练记录（results.csv，epoch 1~10）
const EPOCHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
const TRAIN_BOX_LOSS = [1.09151, 1.15537, 1.16932, 1.14487, 1.11284, 1.05305, 1.01875, 0.98571, 1.00816, 0.97086]
const TRAIN_CLS_LOSS = [0.75822, 0.83819, 0.86447, 0.85081, 0.80004, 0.73498, 0.67899, 0.64224, 0.64239, 0.60904]
const LR_PG0 = [0.000555594, 0.00100125, 0.00133688, 0.0011719, 0.00100687, 0.000841835, 0.000676802, 0.000511769, 0.000346736, 0.000181703]

// 图表配色收敛到 primary + 中性灰
const chartPrimary = '#1D4ED8'
const chartGray = '#94A3B8'

function initCharts() {
  charts.forEach(c => c && c.dispose())
  charts = []

  // 1. 柱状图
  if (barSummaryRef.value) {
    const c1 = echarts.init(barSummaryRef.value)
    c1.setOption({
      backgroundColor: '#ffffff',
      title: {
        text: `最佳轮次 (Epoch ${BEST_EPOCH}) 实测指标`,
        left: 'center',
        top: 5,
        textStyle: { fontSize: 13, color: '#0F172A', fontWeight: 500 }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: '#ffffff',
        borderColor: '#E2E8F0',
        textStyle: { color: '#0F172A', fontSize: 12 }
      },
      grid: { left: '4%', right: '4%', bottom: '5%', top: 50, containLabel: true },
      xAxis: {
        type: 'category',
        data: ['mAP50', 'mAP50-95', 'Precision', 'Recall'],
        axisLine: { lineStyle: { color: '#E2E8F0' } },
        axisTick: { show: false },
        axisLabel: { color: '#475569', fontSize: 12 }
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 1.0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: '#F1F5F9', type: 'dashed' } },
        axisLabel: { color: '#94A3B8' }
      },
      series: [
        {
          name: 'Score',
          type: 'bar',
          barWidth: 84,
          data: [
            { value: 0.786, itemStyle: { borderRadius: [4, 4, 0, 0], color: chartPrimary } },
            { value: 0.525, itemStyle: { borderRadius: [4, 4, 0, 0], color: chartGray } },
            { value: 0.803, itemStyle: { borderRadius: [4, 4, 0, 0], color: chartPrimary } },
            { value: 0.677, itemStyle: { borderRadius: [4, 4, 0, 0], color: chartGray } }
          ],
          label: {
            show: true,
            position: 'top',
            color: '#0F172A',
            fontFamily: 'monospace',
            fontSize: 13,
            distance: 8
          }
        }
      ]
    })
    charts.push(c1)
  }

  // 2. 学习率曲线
  if (lrCurveRef.value) {
    const c2 = echarts.init(lrCurveRef.value)
    // 逐轮实测 lr/pg0（results.csv）；args.yaml 中 cos_lr=False，为线性衰减而非余弦退火
    const epochs = EPOCHS
    const lrValues = LR_PG0

    c2.setOption({
      backgroundColor: '#ffffff',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#ffffff',
        borderColor: '#E2E8F0',
        textStyle: { color: '#0F172A', fontSize: 12 }
      },
      grid: { left: '4%', right: '4%', bottom: '5%', top: 25, containLabel: true },
      xAxis: {
        type: 'category',
        name: 'Epoch',
        data: epochs,
        axisLine: { lineStyle: { color: '#E2E8F0' } },
        axisLabel: { color: '#64748B' }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#F1F5F9', type: 'dashed' } }
      },
      series: [
        {
          name: 'Learning Rate',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: lrValues,
          itemStyle: { color: chartPrimary },
          lineStyle: { width: 2, color: chartPrimary },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(79, 70, 229, 0.15)' },
              { offset: 1, color: 'rgba(79, 70, 229, 0.0)' }
            ])
          }
        }
      ]
    })
    charts.push(c2)
  }

  // 3. Loss 曲线
  if (lossCurveRef.value) {
    const c3 = echarts.init(lossCurveRef.value)
    // 逐轮实测 train/box_loss 与 train/cls_loss（results.csv），非拟合曲线
    const epochs = EPOCHS
    const boxLoss = TRAIN_BOX_LOSS
    const clsLoss = TRAIN_CLS_LOSS

    c3.setOption({
      backgroundColor: '#ffffff',
      tooltip: { trigger: 'axis' },
      legend: { data: ['Box Loss (定位回归)', 'Cls Loss (目标分类)'], top: 0, textStyle: { color: '#475569', fontSize: 12 } },
      grid: { left: '3%', right: '4%', bottom: '3%', top: 40, containLabel: true },
      xAxis: { type: 'category', data: epochs, axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748B' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } },
      series: [
        { name: 'Box Loss (定位回归)', type: 'line', smooth: true, showSymbol: false, data: boxLoss, itemStyle: { color: chartPrimary }, lineStyle: { width: 2 } },
        { name: 'Cls Loss (目标分类)', type: 'line', smooth: true, showSymbol: false, data: clsLoss, itemStyle: { color: chartGray }, lineStyle: { width: 2 } }
      ]
    })
    charts.push(c3)
  }
}

watch(activeTab, async () => {
  await nextTick()
  initCharts()
})

onMounted(async () => {
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
